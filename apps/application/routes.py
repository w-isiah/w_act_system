from apps.application import blueprint
from flask import render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re  # <-- Add this line
from apps import get_db_connection
from jinja2 import TemplateNotFound
from flask import Blueprint, render_template, flash
from datetime import datetime
import pytz
from flask import jsonify


def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)




@blueprint.route('/application')
def application():
    """
    Fetch activation keys joined with subscription plan details.
    Render the activation key management page.
    """
    activation_data = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                ak.id AS activation_id,
                ak.activation_key,
                ak.mac_address,
                ak.device_id,
                ak.created_at,
                sp.plan_id,
                sp.name AS plan_name,
                sp.price,
                sp.billing_cycle,
                sp.duration_in_days,
                sp.is_active
            FROM activation_keys ak
            INNER JOIN subscription_plans sp ON ak.subscription_plan_id = sp.plan_id
            ORDER BY ak.created_at DESC
        """
        cursor.execute(query)
        activation_data = cursor.fetchall()

    except Exception as e:
        flash(f"Error fetching activation keys: {str(e)}", "danger")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template(
        'application/application.html',
        activation_data=activation_data,
        segment='application'
    )













def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)







@blueprint.route('/add_activation_key', methods=['GET', 'POST'])
def add_activation_key():
    import random
    import string

    def generate_activation_key(length=24):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        activation_key = generate_activation_key()
        subscription_plan_id = request.form.get('subscription_plan_id', '').strip()
        mac_address = request.form.get('mac_address', '').strip()
        device_id = request.form.get('device_id', '').strip()
        created_at = get_kampala_time().date()

        if not subscription_plan_id:
            flash("Subscription plan is required.", "warning")
        else:
            try:
                # Ensure uniqueness
                check_query = "SELECT * FROM activation_keys WHERE activation_key = %s"
                cursor.execute(check_query, (activation_key,))
                while cursor.fetchone():
                    activation_key = generate_activation_key()

                insert_query = """
                    INSERT INTO activation_keys (
                        activation_key, subscription_plan_id, mac_address, device_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (
                    activation_key, subscription_plan_id, mac_address, device_id, created_at
                ))
                connection.commit()
                flash(f"Activation key '{activation_key}' successfully generated and saved!", "success")
                return redirect(url_for('application_blueprint.application'))

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    # GET: Load available plans
    try:
        cursor.execute("SELECT plan_id, name FROM subscription_plans WHERE is_active = 1")
        plans = cursor.fetchall()
        activation_key = generate_activation_key()

    except mysql.connector.Error as err:
        flash(f"Failed to load plans: {err}", "danger")
        plans = []
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template("application/add_activation_key.html", plans=plans,activation_key=activation_key)



















    
@blueprint.route('/edit_activation_key/<int:key_id>', methods=['GET', 'POST'])
def edit_activation_key(key_id):
    """Edit an existing activation key record."""

    # Ensure user is logged in
    if 'id' not in session:
        flash("You must be logged in to access this page.", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['id']
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Fetch current activation key data
        cursor.execute("""
            SELECT ak.*, sp.name AS plan_name
            FROM activation_keys ak
            LEFT JOIN subscription_plans sp ON ak.subscription_plan_id = sp.plan_id
            WHERE ak.id = %s AND sp.user_id = %s
        """, (key_id, user_id))
        activation_key = cursor.fetchone()

        if not activation_key:
            flash("Activation key not found or you don't have permission to edit it.", "danger")
            return redirect(url_for('application_blueprint.application'))

        # Get active subscription plans for the dropdown
        cursor.execute("SELECT plan_id, name FROM subscription_plans WHERE is_active = 1 AND user_id = %s", (user_id,))
        plans = cursor.fetchall()

        if request.method == 'POST':
            subscription_plan_id = request.form.get('subscription_plan_id')
            mac_address = request.form.get('mac_address', '').strip() or None
            device_id = request.form.get('device_id', '').strip() or None

            if not subscription_plan_id:
                flash("Subscription plan is required.", "warning")
            else:
                try:
                    cursor.execute("""
                        UPDATE activation_keys
                        SET subscription_plan_id = %s,
                            mac_address = %s,
                            device_id = %s
                        WHERE id = %s
                    """, (
                        subscription_plan_id,
                        mac_address,
                        device_id,
                        key_id
                    ))
                    connection.commit()
                    flash("Activation key updated successfully!", "success")
                    return redirect(url_for('application_blueprint.application'))

                except mysql.connector.Error as err:
                    flash(f"Database error: {err}", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        'application/edit_activation_key.html',
        activation_key=activation_key,
        plans=plans,
        segment='application'
    )









from apps import csrf




def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/submit_info', methods=['POST'])
@csrf.exempt
def submit_info():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON received"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid JSON: {e}"}), 400

    ip = data.get('ip')
    mac = data.get('mac')
    device_id = data.get('device_id')
    country = data.get('country')
    state = data.get('state')
    received_at = get_kampala_time()

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if device_id already exists
        cursor.execute("SELECT id FROM system_info WHERE device_id = %s", (device_id,))
        existing = cursor.fetchone()

        if existing:
            print("[Server] ⚠️ Device already exists in DB. Skipping insert.")
            return jsonify({"status": "exists", "message": "Device already recorded"}), 200

        # Insert only if new
        cursor.execute("""
            INSERT INTO system_info (ip_address, mac_address, device_id, country, state, received_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ip, mac, device_id, country, state, received_at))
        connection.commit()

    except Exception as e:
        print(f"[Server] ❌ Database error: {e}")
        return jsonify({"status": "error", "message": "Failed to save system info"}), 500
    finally:
        cursor.close()
        connection.close()

    return jsonify({"status": "success", "message": "Info saved"}), 200









@blueprint.route('/computer_info')
def computer_info():
    """
    Fetch system information records from the system_info table.
    Render the computer info management page.
    """
    system_data = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                id,
                ip_address,
                mac_address,
                device_id,
                country,
                state,
                received_at
            FROM system_info
            ORDER BY received_at DESC
        """
        cursor.execute(query)
        system_data = cursor.fetchall()

    except Exception as e:
        flash(f"Error fetching system information: {str(e)}", "danger")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template(
        'application/computer_info.html',  # update this path if using a different template
        system_data=system_data,
        segment='computer_info'
    )













@blueprint.route('/delete_activation_key/<int:key_id>')
def delete_activation_key(key_id):
    """Deletes an activation key from the database by its ID."""

    if 'id' not in session:
        flash("You must be logged in to perform this action.", "warning")
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM activation_keys WHERE id = %s", (key_id,))
        connection.commit()
        flash("Activation key deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting activation key: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('application_blueprint.application'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("application/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'application'

        return segment

    except:
        return None
