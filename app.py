from flask import Flask, request, jsonify, session, redirect, url_for, render_template, send_from_directory
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

# Ensure the folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
@app.route('/')
def main():
    uuid = request.args.get('uuid')
    if uuid:
        if uuid == AUTHORIZED_UUID:
            session['uuid'] = uuid
            return jsonify(
                {
                    "auth_uuid": AUTHORIZED_UUID, 
                    'arg_uuid': uuid,
                    'session_uuid': session.get('uuid'),
                    'match': session.get('uuid') == AUTHORIZED_UUID if uuid else False,
                }
            )
            # return redirect(url_for('reservations'))
        else:
            return redirect(url_for('main'))

    if session.get('uuid') != AUTHORIZED_UUID:
        return redirect(url_for('main'))

    return render_template('instructions.html')

@app.route('/test', methods=['GET'])
def test():
    if session.get('uuid') != AUTHORIZED_UUID:
        return redirect(url_for('main'))

    return jsonify({"message": "Test route is working!"})

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/reservations', methods=['GET', 'POST'])
def reservations():
    # Check if the session UUID matches the authorized UUID
    session_uuid = session.get('uuid')
    if session_uuid != AUTHORIZED_UUID:
        return redirect(url_for('main'))

    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        # create_placards = request.form.get('create_placards') == 'yes'  # This will be True if checked
        
        if uploaded_file and uploaded_file.filename.endswith('.xlsx'):
            # Save the file to the UPLOAD_FOLDER
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
            uploaded_file.save(file_path)

            # Process the file with pyfedcamp.Reservations
            try:
                r = Reservations(
                    input_file=file_path,
                    # create_placards=create_placards,
                    output_dir=app.config['DOWNLOAD_FOLDER'],
                )

                today = datetime.date.today()
                arrival_dates = r.res_df[r.res_df['Arrival Date'].dt.date >= today]['Arrival Date'].dt.date.unique()

                return render_template(
                    'reports.html',
                    file_path=file_path,
                    file_name=file_path.split('/')[-1],
                    arrival_dates=arrival_dates
                )

            except Exception as e:
                return jsonify({"message": f"Error processing file: {str(e)}"}), 500
        
        else:
            return jsonify({"message": "Invalid file type. Please upload an Excel spreadsheet."}), 400

    # Render the upload form
    return render_template('file_upload.html')

@app.route('/placards', methods=['GET', 'POST'])
def placards():
    # Check if the session UUID matches the authorized UUID
    session_uuid = session.get('uuid')
    if session_uuid != AUTHORIZED_UUID:
        return redirect(url_for('main'))

    file_path = request.args.get('file_path')
    arrival_date = request.args.get('arrival_date')

    try:
        r = Reservations(
            input_file=file_path,
            create_placards=True,  
            output_dir=app.config['DOWNLOAD_FOLDER'],
            arrival_dates=[datetime.datetime.strptime(arrival_date, '%Y-%m-%d').date()] if arrival_date else None
        )
    except Exception as e:
        return jsonify({"message": f"Error creating placards: {str(e)}"}), 500

    placards_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'placards.pdf')
    if os.path.exists(placards_path):
        return redirect(url_for('download_file', filename='placards.pdf'))
    else:
        return jsonify({"message": "Error creating placards PDF file for download"}), 403
