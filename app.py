from flask import Flask, request, session, redirect, url_for, render_template, send_from_directory
import os
from pyfedcamp import Reservations
import datetime

app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET')

# Shared UUID for authentication
AUTHORIZED_UUID = os.getenv('AUTHORIZED_UUID')

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER

# Ensure the folders exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
    

@app.route('/')
def main():
    if 'uuid' in request.args:
        session.pop('uuid', None)
        session.pop('file_path', None)

    if 'uuid' in session and 'file_path' in session:
        return redirect(url_for('reports'))
    else:
        uuid = request.args.get('uuid')
        if uuid:
            if uuid == AUTHORIZED_UUID:
                session['uuid'] = uuid
                return redirect(url_for('upload'))
            else:
                return render_template('error.html', message="Unauthorized access. Please provide return to your email invitation and use the provided link.")
        else:
            return render_template('instructions.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'uuid' not in session:
        return redirect(url_for('main'))
    
    if 'file_path' in session:
        return redirect(url_for('reports'))

    if request.method == 'POST':
        uploaded_file = request.files.get('file')

        if uploaded_file and uploaded_file.filename.endswith('.xlsx'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
            uploaded_file.save(file_path)

            # Clear all files from downloads subdirectories
            clear_downloads_folder()

            try:
                r = Reservations(
                    input_file=file_path
                )
                session['file_path'] = file_path
            except Exception as e:
                return render_template('error.html', message=f"Error processing file: {str(e)}")

            # Build reports 
            today = datetime.date.today()
            arrival_dates = r.res_df[r.res_df['Arrival Date'].dt.date >= today]['Arrival Date'].dt.date.unique()
            if arrival_dates.size > 0:
                for arrival_date in arrival_dates:
                    Reservations(
                        input_file=file_path,
                        create_placards=True,
                        arrival_dates=[arrival_date],
                        output_dir=f"{app.config['DOWNLOAD_FOLDER']}/placards",
                        placards_filename=f"{arrival_date}.pdf",
                    )

            return redirect(url_for('reports'))
        else:
            return render_template('error.html', message="Invalid file type. Please upload an Excel spreadsheet.")

    return render_template('file_upload.html')

@app.route('/reports', methods=['GET'])
def reports():
    if 'uuid' not in session:
        return redirect(url_for('main'))

    if 'file_path' not in session:
        return redirect(url_for('upload'))

    file_path = session.get('file_path')

    download_root = app.config['DOWNLOAD_FOLDER']
    sectioned_files = {}

    for root, dirs, files in os.walk(download_root):
        rel_dir = os.path.relpath(root, download_root)
        # Use subfolder as section, skip root folder itself
        section = rel_dir if rel_dir != '.' else 'Other'
        for file in files:
            if section not in sectioned_files:
                sectioned_files[section] = []
            rel_file = os.path.join(rel_dir, file) if rel_dir != '.' else file
            sectioned_files[section].append(rel_file)

    # Optionally, sort sections and files
    for section in sectioned_files:
        sectioned_files[section] = sorted(sectioned_files[section])
    sectioned_files = dict(sorted(sectioned_files.items()))

    return render_template(
        'reports.html',
        file_path=file_path,
        file_name=os.path.basename(file_path),
        sectioned_files=sectioned_files
    )

@app.route('/downloads/<path:filepath>')
def download_file(filepath):
    # filepath can be e.g. "placards/2024-07-01.pdf"
    full_dir = app.config['DOWNLOAD_FOLDER']
    directory = os.path.join(full_dir, os.path.dirname(filepath))
    filename = os.path.basename(filepath)
    return send_from_directory(directory, filename, as_attachment=True)

import shutil

def clear_downloads_folder():
    downloads_root = app.config['DOWNLOAD_FOLDER']
    for root, dirs, files in os.walk(downloads_root):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")