from flask import Flask, request, render_template, send_file, jsonify
import fitz
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB  file size

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    
    for word in doc:
        text += word.get_text("text") + "\n"
    
    return text

def detect_emails(text):
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    detected_text = re.sub(email_pattern, '[ Email ]', text)
    return detected_text

def detect_numbers(text):
    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}'
    detected_text = re.sub(phone_pattern, '[ PhoneNumber ]', text)
    return detected_text

def detect_name(text):
    name_pattern = r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]*|\s[A-Z]{1,3})+\b'
    detected_name = re.sub(name_pattern, '[ Name ]', text)
    return detected_name

def textPdf(text, file):
    try: # To solv ethe problem 
        def clean_text(text):
            replacements = {
                'â€¢': '• ',  
                'â€"': '- ',  
                'â€™': "'",   
                'â€œ': '"',   
                'â€?': '"',   
                '\u2022': '• ',  
                '\u2013': '- ',  
                '\u2014': '- ',  
                '\u2019': "'",   
                '\u201c': '"',   
                '\u201d': '"',   
            }
            
            for old, new in replacements.items():
                text = text.replace(old, new)
            
            cleaned = ''.join(char if ord(char) < 128 else ' ' for char in text)
            
            lines = cleaned.split('\n')
            cleaned_lines = []
            for line in lines:
                line = ' '.join(line.split())  
                if line.strip():  
                    cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)
        
        cleaned_text = clean_text(text)
        
        doc = SimpleDocTemplate(file, pagesize=letter,
                              rightMargin=35, leftMargin=40,
                              topMargin=25, bottomMargin=20)
        
        styles = getSampleStyleSheet()
        
        #custom style
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=12,
            leading=14,
            spaceAfter=11,
            leftIndent=0,
            rightIndent=0,
        )
        
        # Build storeu 
        story = []
        
        lines = cleaned_text.split('\n')
        for line in lines:
            if line.strip():
                line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                para = Paragraph(line, normal_style)
                story.append(para)
                story.append(Spacer(1, 3))
        
        # Build PDF
        doc.build(story)
        print(f"PDF saved successfully as {file}")
        
    except Exception as e:
        print(f"Error in textPdf: {str(e)}")
        try:
            with open(file.replace('.pdf', '.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Fallback: Text file saved as {file.replace('.pdf', '.txt')}")
        except:
            raise Exception(f"PDF generation failed: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            extracted_text = extract_text(filepath)
            
            final1 = detect_emails(extracted_text)
            final2 = detect_numbers(final1)
            final3 = detect_name(final2)
            
            output_filename = f"anonymized_{filename}"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            textPdf(final3, output_path)
            
            os.remove(filepath)
            
            return jsonify({
                'success': True,
                'download_url': f'/download/{output_filename}',
                'preview_text': final3[:500] + "..." if len(final3) > 500 else final3
            })
            
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Error processing PDF: {str(e)}'}), 500
    
    return jsonify({'error': 'Please upload a valid PDF file'}), 400

@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True)