from apps.home import blueprint
from flask import render_template, request, session, flash, redirect, url_for
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound
from apps import get_db_connection
import logging

from flask import render_template, redirect, url_for, flash
from apps import get_db_connection
from datetime import datetime





@blueprint.route('/index')
def index():
    if 'id' not in session:
        # If the session ID is not present, redirect to the login page
        flash('Login required to access this page.', 'error')
        return redirect(url_for('authentication_blueprint.login'))

    try:
        # Get DB connection using context manager
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                # Retrieve the user by ID from the session
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['id'],))
                user = cursor.fetchone()

                if not user: 
                    # If the user is not found, prompt to log in again
                    flash('User not found. Please log in again.', 'error')
                    return redirect(url_for('authentication_blueprint.login'))

                # Role-based rendering
                if user['role'] in ['admin', 'director']:
                    return render_template('home/index.html', segment='index')
                elif user['role'] == 'user':
                    return render_template('home/user_index.html', segment='index')
               
                # If no matching role found, prompt to log in again
                flash('User not found. Please log in again.', 'error')
                return redirect(url_for('authentication_blueprint.login'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('authentication_blueprint.login'))  # Redirect to login page in case of error






@blueprint.route('/<template>')
def route_template(template):
    """
    Renders dynamic templates from the 'home' folder.
    """
    try:
        if not template.endswith('.html'):
            template += '.html'
        
        segment = get_segment(request)
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        logging.error(f"Template {template} not found")
        return render_template('home/page-404.html', segment=segment), 404

    except Exception as e:
        logging.error(f"Error rendering template {template}: {str(e)}")
        return render_template('home/page-500.html', segment=segment), 500

def get_segment(request):
    """
    Extracts the last part of the URL path to identify the current page.
    """
    segment = request.path.strip('/').split('/')[-1]
    if not segment:
        segment = 'index'
    return segment
