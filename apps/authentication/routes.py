from flask import (
    render_template, redirect, request, url_for, flash, session, current_app, jsonify
)
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from PIL import Image
import os
import mysql.connector

from apps import get_db_connection
from apps.authentication import blueprint


from datetime import datetime
import pytz
def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)



def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']



@blueprint.route('/', methods=['GET', 'POST'])
def route_default():
    return redirect(url_for('authentication_blueprint.login'))






@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            with get_db_connection() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                    user = cursor.fetchone()

                    if user:
                        if user['password'] == password:  # Note: no hashing here, consider adding hashing in future
                            try:
                                current_time = get_kampala_time()

                                # Insert a new login record with Kampala time
                                cursor.execute(
                                    "INSERT INTO user_activity (user_id, login_time) VALUES (%s, %s)", 
                                    (user['id'], current_time)
                                )
                                
                                # Set user as online
                                cursor.execute("UPDATE users SET is_online = 1 WHERE id = %s", (user['id'],))
                                connection.commit()

                                # Update session
                                session.update({
                                    'loggedin': True,
                                    'id': user['id'],
                                    'username': user['username'],
                                    'profile_image': user.get('profile_image'),
                                    'first_name': user.get('first_name'),
                                    'role': user.get('role'),
                                    'last_activity': current_time
                                })
                                session.permanent = True

                                print(f"Session updated with user_id: {session.get('id')}")

                                flash('Login successful!', 'success')
                                return redirect(url_for('home_blueprint.index'))

                            except Exception as e:
                                print(f"Error during session handling or user activity logging: {str(e)}")
                                flash('An error occurred during the login process. Please try again later.', 'danger')
                                return redirect(url_for('authentication_blueprint.login'))
                        else:
                            flash('Incorrect password.', 'danger')
                            return redirect(url_for('authentication_blueprint.login'))
                    else:
                        flash('Username not found', 'danger')
                        return redirect(url_for('authentication_blueprint.login'))

        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')

    return render_template('accounts/login.html')













@blueprint.before_app_request
def check_inactivity():
    """Check for session timeout due to inactivity."""
    if 'loggedin' in session:
        last_activity_str = session.get('last_activity')
        if last_activity_str:
            try:
                # Parse ISO 8601 string with timezone info
                last_activity = datetime.fromisoformat(last_activity_str)
            except Exception:
                last_activity = None

            current_time = get_kampala_time()

            if last_activity:
                time_diff = current_time - last_activity
                # Timeout after 30 minutes of inactivity
                if time_diff > timedelta(minutes=30):
                    try:
                        with get_db_connection() as connection:
                            with connection.cursor(dictionary=True) as cursor:
                                # Strip tzinfo before storing in MariaDB DATETIME
                                logout_time_naive = current_time.replace(tzinfo=None)

                                cursor.execute("""
                                    UPDATE user_activity 
                                    SET logout_time = %s 
                                    WHERE user_id = %s AND logout_time IS NULL
                                """, (logout_time_naive, session['id']))

                                cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (session['id'],))
                                connection.commit()

                        session.clear()
                        flash('Session expired due to inactivity.', 'warning')
                        return redirect(url_for('authentication_blueprint.login'))
                    except Exception as e:
                        flash(f"An error occurred while updating the logout status: {str(e)}", 'danger')
                        session.clear()
                        return redirect(url_for('authentication_blueprint.login'))

        # Update last_activity timestamp on each request as ISO string with timezone
        session['last_activity'] = get_kampala_time().isoformat()













@blueprint.route('/logout')
def logout():
    user_id = session.get('id')
    username = session.get('username')

    print(f"Logout called for user_id: {user_id}, username: {username}")

    if user_id and username:
        try:
            with get_db_connection() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    current_time = get_kampala_time()
                    current_time_naive = current_time.replace(tzinfo=None)

                    print(f"Updating user_activity logout_time for user_id={user_id} to {current_time_naive}")
                    cursor.execute("""
                        UPDATE user_activity 
                        SET logout_time = %s 
                        WHERE user_id = %s AND logout_time IS NULL
                    """, (current_time_naive, user_id))

                    print(f"Setting is_online = 0 for user_id={user_id}")
                    cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (user_id,))

                    connection.commit()
                    print(f"User '{username}' logged out successfully.")

        except Exception as e:
            print(f"Exception in logout route: {e}")
            flash(f"An error occurred while updating the logout status: {str(e)}", 'danger')

    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('authentication_blueprint.login'))










@blueprint.route('/manage_users')
def manage_users():
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                # Check if the user has admin privileges
                if session.get('role') == 'admin':
                    cursor.execute("SELECT * FROM users WHERE role != 'admin'")
                elif session.get('role') == 'inventory_manager':
                    cursor.execute("SELECT * FROM users WHERE role != 'admin' AND role != 'inventory_manager' AND role != 'class_teacher' ")

                else:
                    flash('You do not have permission to access this page.', 'warning')
                    return redirect(url_for('authentication_blueprint.login'))

                users = cursor.fetchall()
                num = len(users)

    except Exception as e:
        flash(f"Error fetching data: {str(e)}", 'danger')
        return redirect(url_for('home_blueprint.index'))

    return render_template('accounts/manage_users.html', num=num, users=users)




@blueprint.route('/get_user_status/<int:user_id>', methods=['GET'])
def get_user_status(user_id):
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT is_online FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if user:
                    status = 'online' if user['is_online'] else 'offline'
                    print(f"[DEBUG] User {user_id} status: {status}")
                    return jsonify({'status': status})
                else:
                    print(f"[DEBUG] User {user_id} not found")
                    return jsonify({'status': 'offline'})
    except Exception as e:
        print(f"[ERROR] get_user_status error: {e}")
        return jsonify({'status': 'offline'})







@blueprint.route('/activity_logs/<int:id>', methods=['GET', 'POST'])
def activity_logs(id):
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                # SQL JOIN query to combine user_activity and users tables
                query = """
                SELECT ua.login_time, ua.logout_time, u.username, u.first_name, u.last_name
                FROM user_activity ua
                JOIN users u ON ua.user_id = u.id
                WHERE ua.user_id = %s
                ORDER BY ua.login_time DESC
                """
                cursor.execute(query, (id,))
                activities = cursor.fetchall()

                return render_template('accounts/activity_logs.html', activities=activities)
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('authentication_blueprint.index'))









# Add user
@blueprint.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        other_name = request.form['other_name']
        
        # Handle profile image upload (if present)
        profile_image = None
        if 'profile_image' in request.files:
            image_file = request.files['profile_image']
            if image_file and allowed_file(image_file.filename):
                profile_image = handle_image_upload(image_file)

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                # Check if the username already exists
                cursor.execute('SELECT 1 FROM users WHERE username = %s', (username,))
                if cursor.fetchone():
                    flash('Username already exists. Please choose a different one.', 'danger')
                    return render_template('accounts/add_user.html', role=session.get('role'), username=session.get('username'))

                try:
                    cursor.execute(''' 
                        INSERT INTO users (username, password, role, first_name, last_name, other_name, profile_image)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (username, password, role, first_name, last_name, other_name, profile_image))
                    connection.commit()
                    flash('User added successfully!', 'success')
                except mysql.connector.Error as err:
                    flash(f'Error: {err}', 'danger')

        return redirect(url_for('home_blueprint.index'))  # Redirect to user management page

    return render_template("accounts/add_user.html", role=session.get('role'), username=session.get('username'))


# Handle the form submission












@blueprint.route('/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                # Getting user data from the form
                username = request.form['username']
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                other_name = request.form['other_name']
                password = request.form['password']
                role = request.form['role']
                profile_image = request.files.get('profile_image')

                # Use the existing password if none is provided
                password = password if password else get_user_password(cursor, id)

                # Handle profile image if uploaded
                profile_image_path = handle_profile_image(cursor, profile_image, id)

                # Update the user information in the database
                try:
                    cursor.execute(''' 
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, other_name = %s, password = %s, role = %s, 
                            profile_image = %s
                        WHERE id = %s
                    ''', (
                        username, first_name, last_name, other_name, password, role, 
                        profile_image_path, id
                    ))
                    connection.commit()
                    flash('User updated successfully!', 'success')
                except mysql.connector.Error as err:
                    flash(f'Error: {err}', 'danger')

                return redirect(url_for('home_blueprint.index'))  # Redirect back to the home page or user list

            # Retrieve the user information from the database to pre-fill the form
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

    return render_template("accounts/edit_user.html", user=user)
















@blueprint.route('/view_user/<int:id>', methods=['GET'])
def view_user(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            # Retrieve the user information based on the user ID
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Join sub_category and category_list to fetch the category name along with sub-category details
            cursor.execute('''
                SELECT sub.sub_category_id, sub.name AS sub_category_name, sub.description AS sub_category_description, 
                       cat.name AS category_name
                FROM sub_category sub
                JOIN category_list cat ON sub.category_id = cat.CategoryID
            ''')
            all_sub_categories = cursor.fetchall()

            # Fetch the sub_category_ids associated with the user from the other_roles table
            cursor.execute('SELECT sub_category_id FROM other_roles WHERE user_id = %s', (id,))
            user_sub_category_ids = {row['sub_category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/view_user.html",
        user=user,
        all_sub_categories=all_sub_categories,
        user_sub_category_ids=user_sub_category_ids
    )





@blueprint.route('/edit_user_roles/<int:id>', methods=['GET', 'POST'])
def edit_user_roles(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                # Retrieve the list of selected sub_category_ids from the form
                selected_sub_categories = request.form.getlist('sub_categories')

                # Clear the previous roles for the user in the other_roles table
                cursor.execute('DELETE FROM other_roles WHERE user_id = %s', (id,))
                connection.commit()

                # Add the newly selected roles to the other_roles table
                for sub_category_id in selected_sub_categories:
                    cursor.execute('''
                        INSERT INTO other_roles (user_id, sub_category_id) 
                        VALUES (%s, %s)
                    ''', (id, sub_category_id))
                connection.commit()

                flash('User roles updated successfully!', 'success')
                return redirect(url_for('authentication_blueprint.manage_users'))

            # Retrieve the user information to pre-fill the form
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Get all sub-categories to display
            cursor.execute('SELECT * FROM sub_category')
            all_sub_categories = cursor.fetchall()

            # Get the current sub-categories assigned to the user
            cursor.execute('SELECT sub_category_id FROM other_roles WHERE user_id = %s', (id,))
            user_sub_category_ids = {row['sub_category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/edit_user_roles.html", 
        user=user, 
        all_sub_categories=all_sub_categories, 
        user_sub_category_ids=user_sub_category_ids
    )










@blueprint.route('/view_user_cat_roles/<int:id>', methods=['GET'])
def view_user_cat_roles(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            # Retrieve the user information based on the user ID
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Fetch all categories
            cursor.execute('SELECT CategoryID, name, description FROM category_list')
            all_categories = cursor.fetchall()

            # Fetch the category_ids associated with the user from the category_roles table
            cursor.execute('SELECT category_id FROM category_roles WHERE user_id = %s', (id,))
            user_category_ids = {row['category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/view_user_cat_roles.html",
        user=user,
        all_categories=all_categories,
        user_category_ids=user_category_ids
    )










@blueprint.route('/edit_user_cat_roles/<int:id>', methods=['GET', 'POST'])
def edit_user_cat_roles(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                # Retrieve the list of selected category_ids from the form
                selected_categories = request.form.getlist('categories')

                # Clear previous category roles for the user
                cursor.execute('DELETE FROM category_roles WHERE user_id = %s', (id,))
                connection.commit()

                # Insert the newly selected categories
                for category_id in selected_categories:
                    cursor.execute('''
                        INSERT INTO category_roles (user_id, category_id) 
                        VALUES (%s, %s)
                    ''', (id, category_id))
                connection.commit()

                flash('User category roles updated successfully!', 'success')
                return redirect(url_for('authentication_blueprint.manage_users'))

            # Retrieve user info
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Get all categories
            cursor.execute('SELECT * FROM category_list')
            all_categories = cursor.fetchall()

            # Get current categories assigned to the user
            cursor.execute('SELECT category_id FROM category_roles WHERE user_id = %s', (id,))
            user_category_ids = {row['category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/edit_user_cat_roles.html", 
        user=user, 
        all_categories=all_categories, 
        user_category_ids=user_category_ids
    )


















def get_user_password(cursor, user_id):
    cursor.execute('SELECT password FROM users WHERE id = %s', (user_id,))
    return cursor.fetchone()['password']


def handle_profile_image(cursor, profile_image, user_id):
    if profile_image and allowed_file(profile_image.filename):
        filename = secure_filename(profile_image.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        profile_image.save(file_path)
        return filename
    else:
        cursor.execute('SELECT profile_image FROM users WHERE id = %s', (user_id,))
        return cursor.fetchone()['profile_image']





@blueprint.route('/api/user/profile-image')
def profile_image():
    if 'profile_image' in session:
        return jsonify({
            'profile_image': session['profile_image']
        })
    else:
        return jsonify({'error': 'Not logged in'}), 401




# Route for deleting a user
@blueprint.route('/delete_user/<int:id>', methods=['GET'])
def delete_user(id):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute('DELETE FROM users WHERE id = %s', (id,))
                connection.commit()
                flash('User deleted successfully!', 'success')
            except mysql.connector.Error as err:
                flash(f'Error: {err}', 'danger')

    return redirect(url_for('home_blueprint.index'))




def handle_image_upload(image_file):
    filename = secure_filename(image_file.filename)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    profile_image_path = os.path.join(upload_folder, filename)

    try:
        img = Image.open(image_file)
        max_width, max_height = 500, 500
        width, height = img.size
        if width > max_width or height > max_height:
            img.thumbnail((max_width, max_height))
            img.save(profile_image_path, optimize=True, quality=85)
        else:
            img.save(profile_image_path)
    except Exception as e:
        flash(f"Error processing image: {e}", 'danger')
        return None

    # Return filename or relative path as per your app needs
    return filename






@blueprint.route('/edit_user_profile/<int:id>', methods=['GET', 'POST'])
def edit_user_profile(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            
            # POST request - Handle profile update
            if request.method == 'POST':
                # Collect form data
                username = request.form['username']
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                other_name = request.form['other_name']
                password = request.form['password']
                profile_image = request.files.get('profile_image')

                # Use existing password if none is provided
                password = password if password else get_user_password(cursor, id)
                
                # Process profile image
                profile_image_path = handle_profile_image(cursor, profile_image, id)

                try:
                    # Update user details in the database
                    cursor.execute(''' 
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, other_name = %s, password = %s, profile_image = %s
                        WHERE id = %s
                    ''', (username, first_name, last_name, other_name, password, profile_image_path, id))
                    connection.commit()
                    flash('User updated successfully!', 'success')
                except mysql.connector.Error as err:
                    flash(f'Error: {err}', 'danger')

                # Redirect after successful update
                return redirect(url_for('home_blueprint.index'))

            # GET request - Fetch user data to populate the edit form
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # If user not found, show error and redirect
            if not user:
                flash('User not found!', 'danger')
                return redirect(url_for('home_blueprint.index'))

    return render_template('accounts/edit_user_profile.html', user=user)










# Error Handlers
@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403

@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404

@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
