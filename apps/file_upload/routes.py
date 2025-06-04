from apps.file_upload import blueprint
from flask import render_template, request, redirect, url_for, flash, session,current_app
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


ALLOWED_EXTENSIONS = {'exe'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS







ALLOWED_EXTENSIONS = {'exe'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/file_upload', methods=['GET', 'POST'])
def file_upload():
    user_id = session.get('id')
    if not user_id:
        flash("User not logged in.", "danger")
        return redirect('/login')  # Adjust to your login route

    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/exe_files')
    os.makedirs(upload_folder, exist_ok=True)

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)

        exe_file = request.files['file']

        if exe_file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        if exe_file and allowed_file(exe_file.filename):
            filename = secure_filename(exe_file.filename)

            # Remove old .exe files
            for existing_file in os.listdir(upload_folder):
                if existing_file.lower().endswith('.exe'):
                    try:
                        os.remove(os.path.join(upload_folder, existing_file))
                    except Exception as e:
                        current_app.logger.error(f"Error deleting file {existing_file}: {e}")

            file_path = os.path.join(upload_folder, filename)
            exe_file.save(file_path)

            uploaded_at = get_kampala_time()

            try:
                with get_db_connection() as connection:
                    with connection.cursor(dictionary=True) as cursor:
                        cursor.execute(
                            """
                            INSERT INTO uploaded_files (filename, uploaded_at, user_id)
                            VALUES (%s, %s, %s)
                            """,
                            (filename, uploaded_at, user_id)
                        )
                    connection.commit()
                flash(f'File "{filename}" uploaded successfully.', 'success')
            except Exception as e:
                current_app.logger.error(f"Database error: {e}")
                flash('Database error during upload.', 'danger')
                return redirect(request.url)
        else:
            flash('Invalid file type. Only .exe files are allowed.', 'danger')
            return redirect(request.url)

    # GET: fetch the latest uploaded file for the user
    uploaded_file = None
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT filename, uploaded_at FROM uploaded_files
                    WHERE user_id = %s
                    ORDER BY uploaded_at DESC
                    LIMIT 1
                    """,
                    (user_id,)
                )
                uploaded_file = cursor.fetchone()
    except Exception as e:
        current_app.logger.error(f"Error fetching uploaded file: {e}")

    return render_template('file_upload/file_upload.html', uploaded_file=uploaded_file)







@blueprint.route('/delete_file', methods=['POST'])
def delete_file():
    user_id = session.get('id')
    filename = request.form.get('filename')

    if not user_id or not filename:
        flash('Invalid request.', 'danger')
        return redirect(url_for('file_upload_blueprint.file_upload'))

    try:
        # Delete file from filesystem
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/exe_files')
        file_path = os.path.join(upload_folder, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete from database
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM uploaded_files WHERE filename = %s AND user_id = %s", (filename, user_id))
            connection.commit()

        flash(f'File "{filename}" has been deleted.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}")
        flash("An error occurred while deleting the file.", "danger")

    return redirect(url_for('file_upload_blueprint.file_upload'))








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
