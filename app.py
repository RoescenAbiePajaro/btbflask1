# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import subprocess  # Add this import for running external scripts
from VirtualPainter import painter_bp



app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.register_blueprint(painter_bp, url_prefix='/painter')
# app.secret_key = 'your_secret_key_here'  # Change this for production!

# Configuration
CORRECT_CODE = "12345"
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def loading_screen():
    """Initial loading screen."""
    session['loading_progress'] = 0
    session['loading_complete'] = False
    return render_template('loading.html')


@app.route('/loading-progress')
def loading_progress():
    """Fake loading progress for UX animation."""
    session['loading_progress'] = session.get('loading_progress', 0) + 10

    if session['loading_progress'] >= 100:
        session['loading_complete'] = True
        return jsonify(progress=100, complete=True)

    return jsonify(progress=session['loading_progress'], complete=False)


@app.route('/entry')
def entry_page():
    """Code entry screen, only accessible after loading."""
    if not session.get('loading_complete', False):
        return redirect(url_for('loading_screen'))

    return render_template('entry.html')


@app.route('/verify', methods=['POST'])
def verify_code():
    """Handle code verification and role assignment."""
    entered_code = request.form.get('code')
    role = request.form.get('role', 'student')

    if entered_code == CORRECT_CODE:
        session['authenticated'] = True
        session['role'] = role

        # Launch VirtualPainter.py in a separate process
        try:
            # Assuming VirtualPainter.py is in the same directory
            subprocess.Popen(['python', 'VirtualPainter.py'])
        except Exception as e:
            print(f"Failed to launch VirtualPainter: {e}")

        return redirect(url_for('launch_page'))
    else:
        flash('Incorrect access code. Please try again.', 'error')
        return redirect(url_for('entry_page'))

@app.route('/index')
def launch_page():
    """Render launch.html after successful authentication."""
    if not session.get('authenticated', False):
        return redirect(url_for('entry_page'))

    role = session.get('role', 'student')
    return render_template('index.html', role=role, video_feed_url="http://localhost:5000/video_feed")


if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Start Flask development server
    app.run(debug=True)