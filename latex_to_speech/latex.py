import os
import re
import uuid
import torch
import pytesseract
import fitz  # PyMuPDF for PDF reading
from gtts import gTTS
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from transformers import T5ForConditionalGeneration, T5Tokenizer

app = Flask(__name__, template_folder='.')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  

for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

model = None
tokenizer = None

def load_model():
    global model, tokenizer
    if model is None:
        print("Loading LaTeX conversion model...")
        tokenizer = T5Tokenizer.from_pretrained("Hyeonsieun/GTtoNT_addmoretoken_ver2")
        model = T5ForConditionalGeneration.from_pretrained("Hyeonsieun/GTtoNT_addmoretoken_ver2").to(device)
        print("Model loaded successfully")

# Function to extract text from PDF using OCR or embedded text
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc):
                print(f"Processing page {page_num+1}/{len(doc)}")
                page_text = page.get_text("text")
                
                # If page has no text, try OCR (optional)
                if not page_text.strip():
                    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                    img_data = pix.tobytes("png")
                    # TODO: Implement OCR if needed
                
                text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text: {e}")
        
    return text

# LaTeX regex pattern
latex_pattern = r"(\\\(.+?\\\)|\\\[.+?\\\]|\\begin\{equation\}.+?\\end\{equation\})"

# Function to convert LaTeX equations to speech using T5
def convert_latex_to_speech(latex_text):
    load_model()
    
    # Clean the LaTeX
    cleaned_latex = latex_text.replace('\\(', '').replace('\\)', '').replace('\\[', '').replace('\\]', '')
    cleaned_latex = re.sub(r'\\begin\{equation\}(.*?)\\end\{equation\}', r'\1', cleaned_latex, flags=re.DOTALL)
    
    input_text = f"translate the LaTeX equation to a text pronouncing the formula: ${cleaned_latex}$"
    inputs = tokenizer.encode(input_text, return_tensors="pt", max_length=325, truncation=True).to(device)
    
    with torch.no_grad():
        output_ids = model.generate(inputs, max_length=325, num_beams=5, early_stopping=True)
    
    output_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return output_text

# Function to replace LaTeX equations with readable text
def process_text(text):
    sentence_list = re.split(f'({latex_pattern})', text)
    processed_sentences = []
    
    for sentence in sentence_list:
        if re.match(latex_pattern, sentence):
            try:
                converted_text = convert_latex_to_speech(sentence)
                processed_sentences.append(f"[EQUATION: {converted_text}]")
            except Exception as e:
                print(f"Error processing equation {sentence}: {e}")
                processed_sentences.append(f"[EQUATION]")
        else:
            processed_sentences.append(sentence)
    
    return "".join(processed_sentences)

# Function to generate speech from text using gTTS
def text_to_speech(text, output_path="output.mp3", language='en', slow=False):
    if not text.strip():
        print("Warning: Input text is empty. No audio will be generated.")
        return None
    
    try:
        tts = gTTS(text=text, lang=language, slow=slow)
        tts.save(output_path)
        return output_path
    except Exception as e:
        print(f"Error generating speech: {e}")
        return None

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        # Create unique filename to prevent collisions
        filename = str(uuid.uuid4()) + '.pdf'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Extract text from PDF
            extracted_text = extract_text_from_pdf(filepath)
            
            # Store text for later processing
            session_id = str(uuid.uuid4())
            text_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            
            # Return text preview and session ID for later processing
            preview = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'preview': preview,
                'total_length': len(extracted_text)
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Only PDF files are allowed'}), 400

@app.route('/process', methods=['POST'])
def process_file():
    data = request.json
    session_id = data.get('session_id')
    voice_settings = data.get('voice_settings', {})
    
    if not session_id:
        return jsonify({'error': 'Missing session ID'}), 400
    
    try:
        # Load extracted text
        text_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.txt")
        with open(text_path, 'r', encoding='utf-8') as f:
            extracted_text = f.read()
        
        # Process LaTeX equations
        processed_text = process_text(extracted_text)
        
        # Generate audio
        output_filename = f"{session_id}.mp3"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        # Apply voice settings
        language = voice_settings.get('language', 'en')
        slow = voice_settings.get('slow', False)
        
        text_to_speech(processed_text, output_path, language=language, slow=slow)
        
        return jsonify({
            'success': True,
            'audio_url': f'/audio/{output_filename}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/audio/<filename>')
def get_audio(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
