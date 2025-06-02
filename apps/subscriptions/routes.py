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





















# View all users for subscription control
@blueprint.route('/manage_subscriptions')
def manage_subscriptions():
    users = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                u.id AS user_id,
                u.username,
                CONCAT_WS(' ', u.first_name, u.other_name, u.last_name) AS full_name,
                u.email,
                IFNULL(s.status, 'not_subscribed') AS status,
                s.subscribed_at,
                s.unsubscribed_at
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.id
            WHERE u.role != 'admin'
        """
        cursor.execute(query)
        users = cursor.fetchall()

    except Exception as e:
        flash(f"Error loading users: {str(e)}", "danger")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template('subscriptions/manage_subscriptions.html', users=users)








# Toggle subscription
@blueprint.route('/toggle_subscription/<int:user_id>', methods=['POST'])
def toggle_subscription(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if subscription exists
        cursor.execute("SELECT id, status FROM subscriptions WHERE user_id = %s", (user_id,))
        record = cursor.fetchone()

        if record:
            sub_id, current_status = record
            if current_status == 'subscribed':
                # Unsubscribe
                cursor.execute("""
                    UPDATE subscriptions
                    SET status = 'not_subscribed', unsubscribed_at = NOW()
                    WHERE id = %s
                """, (sub_id,))
            else:
                # Subscribe
                cursor.execute("""
                    UPDATE subscriptions
                    SET status = 'subscribed', subscribed_at = NOW(), unsubscribed_at = NULL
                    WHERE id = %s
                """, (sub_id,))
        else:
            # Create subscription if it doesn't exist
            cursor.execute("""
                INSERT INTO subscriptions (user_id, status, subscribed_at)
                VALUES (%s, 'subscribed', NOW())
            """, (user_id,))

        connection.commit()
        flash("Subscription updated successfully.", "success")

    except Exception as e:
        flash(f"Error updating subscription: {str(e)}", "danger")
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
