from apps.subscriptions import blueprint
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







@blueprint.route('/manage_subscriptions')
def manage_subscriptions():
    users = []
    subscription_plans = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch subscription plans
        cursor.execute("""
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
        """)
        subscription_plans = cursor.fetchall()

        # Fetch users and their subscription info
        cursor.execute("""
            SELECT 
                u.id AS user_id,
                u.username,
                CONCAT_WS(' ', u.first_name, u.other_name, u.last_name) AS full_name,
                u.email,
                IFNULL(s.status, 'not_subscribed') AS status,
                s.subscribed_at,
                s.unsubscribed_at,
                sp.name AS plan_name,
                sp.price AS plan_price,
                sp.billing_cycle,
                sp.duration_in_days
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.id
            LEFT JOIN subscription_plans sp ON s.subscription_plan_id = sp.plan_id
            WHERE u.role != 'admin'
        """)
        users = cursor.fetchall()

    except Exception as e:
        flash(f"Error loading subscriptions: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('subscriptions/manage_subscriptions.html', 
                           subscription_plans=subscription_plans,
                           users=users)





@blueprint.route('/toggle_subscription/<int:user_id>', methods=['POST'])
def toggle_subscription(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if subscription exists for user
        cursor.execute("SELECT id, status FROM subscriptions WHERE user_id = %s", (user_id,))
        record = cursor.fetchone()

        # Extract selected subscription plan from form data (if any)
        selected_plan_id = None
        if 'subscription_plan_id' in request.form:
            selected_plan_id = request.form.get('subscription_plan_id')
            if selected_plan_id == '':
                selected_plan_id = None

        if record:
            sub_id, current_status = record

            if current_status == 'subscribed':
                # Deactivate subscription: clear plan and mark unsubscribed
                cursor.execute("""
                    UPDATE subscriptions
                    SET status = 'not_subscribed',
                        unsubscribed_at = NOW(),
                        subscription_plan_id = NULL
                    WHERE id = %s
                """, (sub_id,))
                connection.commit()
                flash("Subscription deactivated successfully.", "success")

            else:
                # Activate subscription - require plan selection
                if not selected_plan_id:
                    flash("Please activate with a subscription plan.", "warning")
                    return redirect(url_for('subscriptions_blueprint.manage_subscriptions'))

                cursor.execute("""
                    UPDATE subscriptions
                    SET status = 'subscribed',
                        subscribed_at = NOW(),
                        unsubscribed_at = NULL,
                        subscription_plan_id = %s
                    WHERE id = %s
                """, (selected_plan_id, sub_id))
                connection.commit()
                flash("Subscription activated successfully.", "success")

        else:
            # No subscription exists - create new if plan selected
            if not selected_plan_id:
                flash("Please activate with a subscription plan.", "warning")
                return redirect(url_for('subscriptions_blueprint.manage_subscriptions'))

            cursor.execute("""
                INSERT INTO subscriptions (user_id, status, subscribed_at, subscription_plan_id)
                VALUES (%s, 'subscribed', NOW(), %s)
            """, (user_id, selected_plan_id))
            connection.commit()
            flash("Subscription created and activated successfully.", "success")

    except Exception as e:
        flash(f"Error updating subscription: {str(e)}", "danger")

    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return redirect(url_for('subscriptions_blueprint.manage_subscriptions'))








@blueprint.route('/change_plan/<int:user_id>', methods=['POST'])
def change_plan(user_id):
    try:
        subscription_plan_id = request.form.get('subscription_plan_id', type=int)
        if not subscription_plan_id:
            flash("Please select a valid subscription plan.", "warning")
            return redirect(url_for('subscriptions_blueprint.manage_subscriptions'))

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Ensure user has a subscription and is subscribed
        cursor.execute("SELECT id, status FROM subscriptions WHERE user_id = %s", (user_id,))
        subscription = cursor.fetchone()

        if not subscription or subscription['status'] != 'subscribed':
            flash("User does not have an active subscription to update.", "warning")
            return redirect(url_for('subscriptions_blueprint.manage_subscriptions'))

        # Update subscription plan only
        cursor.execute("""
            UPDATE subscriptions
            SET subscription_plan_id = %s
            WHERE id = %s
        """, (subscription_plan_id, subscription['id']))

        connection.commit()
        flash("Subscription plan updated successfully.", "success")

    except Exception as e:
        flash(f"Error updating subscription plan: {str(e)}", "danger")

    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return redirect(url_for('subscriptions_blueprint.manage_subscriptions'))







@blueprint.route('/delete_subscriptions/<int:subscriptions_id>')
def delete_subscriptions(subscriptions_id):
    """Deletes a sub-category from the database by its ID."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Ensure the sub-category exists before attempting deletion (optional but safe)
        cursor.execute('SELECT * FROM subscriptions WHERE subscriptions_id = %s', (subscriptions_id,))
        result = cursor.fetchone()
        if not result:
            flash("Section not found.", "warning")
        else:
            # Delete the sub-category
            cursor.execute('DELETE FROM subscriptions WHERE subscriptions_id = %s', (subscriptions_id,))
            connection.commit()
            flash("Section deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting sub-category: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('subscriptions_blueprint.subscriptions'))













@blueprint.route('/subscriptions_status')
def subscriptions_status():
    current_user_id = session.get('id')
    current_user_subscription = None

    if not current_user_id:
        flash("You must be logged in to view your subscription.", "danger")
        return redirect(url_for("auth_blueprint.login"))  # adjust route name if different

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch the current user's subscription info
        cursor.execute("""
            SELECT 
                s.status,
                s.subscribed_at,
                s.unsubscribed_at,
                sp.name AS plan_name,
                sp.price AS plan_price,
                sp.billing_cycle,
                sp.duration_in_days
            FROM subscriptions s
            JOIN subscription_plans sp ON s.subscription_plan_id = sp.plan_id
            WHERE s.user_id = %s
            ORDER BY s.subscribed_at DESC
            LIMIT 1
        """, (current_user_id,))
        current_user_subscription = cursor.fetchone()

    except Exception as e:
        flash(f"Error fetching subscription: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        'subscriptions/subscriptions_status.html',
        current_user_subscription=current_user_subscription
    )










@blueprint.route('/download_exe')
def download_exe():
    user_id = session.get('id')
    if not user_id:
        flash("Please log in first.", "danger")
        return redirect(url_for("auth_blueprint.login"))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT status FROM subscriptions
            WHERE user_id = %s AND status = 'active'
        """, (user_id,))
        subscription = cursor.fetchone()

        if not subscription:
            flash("You must have an active subscription to download this file.", "warning")
            return redirect(url_for('file_upload_blueprint.file_upload'))

        # Assuming file is stored in configured folder
        exe_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/exe_files')
        latest_file = next((f for f in os.listdir(exe_folder) if f.endswith('.exe')), None)

        if latest_file:
            return send_from_directory(directory=exe_folder, path=latest_file, as_attachment=True)
        else:
            flash("No executable file available for download.", "danger")
            return redirect(url_for('file_upload_blueprint.file_upload'))

    except Exception as e:
        flash(f"Download failed: {e}", "danger")
        return redirect(url_for('file_upload_blueprint.file_upload'))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()








@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("subscriptions/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'subscriptions'

        return segment

    except:
        return None
