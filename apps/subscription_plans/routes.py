from apps.subscription_plans import blueprint
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


def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)




@blueprint.route('/subscription_plans')
def subscription_plans():
    """
    Fetch all subscription plans from the database.
    Render the subscription plans management page.
    """
    subscription_plans = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                plan_id,
                name,
                price,
                billing_cycle,
                duration_in_days,
                is_active,
                created_at,
                updated_at,
                user_id
            FROM subscription_plans
        """
        cursor.execute(query)
        subscription_plans = cursor.fetchall()

    except Exception as e:
        flash(f"Error fetching subscription plans: {str(e)}", "danger")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template(
        'subscription_plans/subscription_plans.html',
        subscription_plans=subscription_plans,
        segment='subscription_plans'
    )













def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/add_subscription_plan', methods=['GET', 'POST'])
def add_subscription_plan():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '0.00').strip()
        billing_cycle = request.form.get('billing_cycle', '').strip()
        duration_in_days = request.form.get('duration_in_days', '').strip()
        is_active = request.form.get('is_active', '1').strip()
        user_id = session.get('id')  # Get user_id from session

        # Validation
        if not name or not billing_cycle or not duration_in_days:
            flash("Name, Billing Cycle, and Duration are required!", "warning")
        elif not re.match(r'^[A-Za-z0-9 _-]+$', name):
            flash("Plan name must contain only letters, numbers, spaces, dashes, or underscores.", "danger")
        elif not user_id:
            flash("You must be logged in to perform this action.", "danger")
        else:
            try:
                # Check for duplicate name or billing cycle
                check_query = """
                    SELECT * FROM subscription_plans WHERE name = %s OR billing_cycle = %s
                """
                cursor.execute(check_query, (name, billing_cycle))
                existing = cursor.fetchone()

                if existing:
                    flash("A plan with this name or billing cycle already exists.", "warning")
                else:
                    now = get_kampala_time().date()
                    insert_query = """
                        INSERT INTO subscription_plans 
                        (name, price, billing_cycle, duration_in_days, is_active, created_at, updated_at, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (
                        name, price, billing_cycle, duration_in_days,
                        is_active, now, now, user_id
                    ))
                    connection.commit()
                    flash("Subscription plan successfully added!", "success")
                    return redirect(url_for('subscription_plans_blueprint.subscription_plans'))

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template("subscription_plans/add_subscription_plans.html")

















    

@blueprint.route('/edit_subscription_plan/<int:plan_id>', methods=['GET', 'POST'])
def edit_subscription_plan(plan_id):
    """Handles editing an existing subscription plan."""

    if 'id' not in session:
        flash("You must be logged in to access this page.", "warning")
        return redirect(url_for('auth.login'))  # Adjust route name if needed

    user_id = session['id']

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the subscription plan to edit
    cursor.execute("SELECT * FROM subscription_plans WHERE plan_id = %s AND user_id = %s", (plan_id, user_id))
    subscription_plan = cursor.fetchone()

    if not subscription_plan:
        cursor.close()
        connection.close()
        flash("Subscription plan not found or you do not have permission to edit it.", "danger")
        return redirect(url_for('subscription_plans_blueprint.subscription_plans'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        billing_cycle = request.form.get('billing_cycle', '').strip()
        duration_in_days = request.form.get('duration_in_days', '').strip()
        is_active = request.form.get('is_active', '1').strip()  # defaults to active

        # Validation
        if not name or not billing_cycle or not price or not duration_in_days:
            flash("All fields except 'is_active' are required!", "warning")
        else:
            try:
                price_val = float(price)
                duration_val = int(duration_in_days)
                is_active_val = bool(int(is_active))
            except ValueError:
                flash("Price must be a number and Duration must be an integer.", "danger")
                return render_template(
                    'subscription_plans/edit_subscription_plans.html',
                    subscription_plan=subscription_plan,
                    segment='subscription_plans'
                )

            try:
                # Check if billing_cycle or name conflict with other plans for this user
                cursor.execute("""
                    SELECT plan_id FROM subscription_plans 
                    WHERE (name = %s OR billing_cycle = %s) AND plan_id != %s AND user_id = %s
                """, (name, billing_cycle, plan_id, user_id))
                existing = cursor.fetchone()

                if existing:
                    flash("Another subscription plan with this name or billing cycle already exists.", "warning")
                else:
                    update_query = """
                        UPDATE subscription_plans
                        SET name = %s,
                            price = %s,
                            billing_cycle = %s,
                            duration_in_days = %s,
                            is_active = %s,
                            updated_at = CURDATE()
                        WHERE plan_id = %s AND user_id = %s
                    """
                    cursor.execute(update_query, (
                        name,
                        price_val,
                        billing_cycle,
                        duration_val,
                        is_active_val,
                        plan_id,
                        user_id
                    ))
                    connection.commit()
                    flash("Subscription plan updated successfully!", "success")
                    return redirect(url_for('subscription_plans_blueprint.subscription_plans'))

            except mysql.connector.Error as e:
                flash(f"Database error: {str(e)}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'subscription_plans/edit_subscription_plans.html',
        subscription_plan=subscription_plan,
        segment='subscription_plans'
    )






















@blueprint.route('/delete_subscription_plan/<int:plan_id>')
def delete_subscription_plan(plan_id):
    """Deletes a subscription plan from the database by its ID."""
    if 'id' not in session:
        flash("You must be logged in to perform this action.", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['id']
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Optionally: Check if the plan belongs to the user (if ownership logic applies)
        cursor.execute('SELECT * FROM subscription_plans WHERE plan_id = %s', (plan_id,))
        plan = cursor.fetchone()
        if not plan:
            flash("Subscription plan not found.", "warning")
        else:
            # Delete the subscription plan
            cursor.execute('DELETE FROM subscription_plans WHERE plan_id = %s', (plan_id,))
            connection.commit()
            flash("Subscription plan deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting subscription plan: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('subscription_plans_blueprint.subscription_plans'))



@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("subscription_plans/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'subscription_plans'

        return segment

    except:
        return None
