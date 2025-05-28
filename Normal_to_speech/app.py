from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
import os
from werkzeug.utils import secure_filename
from math_utils import extract_formulas, formulas_to_speech

app = Flask(__name__)
app.secret_key = 'replace_with_a_random_secret'

# Upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # check file
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            file.save(path)

            # language
            lang = request.form.get('language')

            # extract and convert
            formulas = extract_formulas(path)
            audio_fname = f"{os.path.splitext(fname)[0]}_{lang}.mp3"
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_fname)
            formulas_to_speech(formulas, lang, audio_path)

            return render_template('result.html', audio_file=audio_fname)
    return render_template('index.html')


@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True)