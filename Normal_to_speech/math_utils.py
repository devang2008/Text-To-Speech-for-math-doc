import re
import fitz  # PyMuPDF
from gtts import gTTS

def extract_formulas(pdf_path, formula_pattern=None):
    formulas = []
    with fitz.open(pdf_path) as doc:
        full_text = ''.join(page.get_text('text') + '\n' for page in doc)

    # Named formulas
    name_formula_patterns = [
        r"([\w\s\-'`]+(?:Formula|Equation|Law|Theorem|Lemma|Identity|Inequality|Rule|Principle|Relation))[:\s]+([^\n]+)",
        r"([\w\s\-'`]+):\s*Formula[:\s]+([^\n]+)"
    ]
    for pat in name_formula_patterns:
        for name, formula in re.findall(pat, full_text, re.IGNORECASE):
            name = name.strip()
            formula = formula.strip()
            if re.search(r'[=+\-*/^∫∑√∞]', formula):
                formulas.append((name, formula))

    # Direct equations
    equation_patterns = [
        r'([^=\n]+?)\s*=\s*([^=\n]+?)(?:\n|$)',
        r'([^=\n]+?)\s*[≈≠≤≥]\s*([^=\n]+?)(?:\n|$)'
    ]
    for pat in equation_patterns:
        for l, r in re.findall(pat, full_text):
            expr = f"{l.strip()} = {r.strip()}"
            if re.search(r'[\d+\-*/^]', expr):
                formulas.append((None, expr))

    seen = set()
    unique = []
    for name, f in formulas:
        if f not in seen:
            unique.append((name or 'Unnamed Formula', f))
            seen.add(f)
    return unique

# normalization

def normalize_formula(formula):
    f = formula
    f = f.replace('^', ' to the power of ')
    f = re.sub(r'sqrt\(([^)]+)\)', r'square root of \1', f)
    for sym, word in [('=', ' equals '), ('+', ' plus '), ('-', ' minus '), ('*', ' times '), ('/', ' divided by ')]:
        f = f.replace(sym, word)
    return ' '.join(f.split())

# language configs
LANG_CONFIG = {
    'en': {
        'tts_lang': 'en',
        'common': {
            r'a\^2\s*\+\s*b\^2\s*=\s*c\^2': 'Pythagorean Theorem',
            r'E\s*=\s*mc\^2': "Einstein's Mass-Energy Equivalence",
        },
        'translations': {}
    },
    'hi': {
        'tts_lang': 'hi',
        'common': {
            r'a\^2\s*\+\s*b\^2\s*=\s*c\^2': 'पाइथागोरस प्रमेय',
            r'E\s*=\s*mc\^2': 'आइंस्टाइन का द्रव्यमान-ऊर्जा समतुल्यता',
        },
        'translations': {
            ' equals ': ' बराबर ', ' plus ': ' एवं ', ' minus ': ' घटा ',
            ' times ': ' गुणा ', ' divided by ': ' भाग ', ' to the power of ': ' की घात ',
            ' square root of ': ' वर्गमूल '
        }
    },
    'mr': {
        'tts_lang': 'mr',
        'common': {
            r'a\^2\s*\+\s*b\^2\s*=\s*c\^2': 'पायथागॉरस प्रमेय',
            r'E\s*=\s*mc\^2': 'आइंस्टाईनचे वस्तुमान-ऊर्जासमानता',
        },
        'translations': {
            ' equals ': ' बरोबर ', ' plus ': ' अधिक ', ' minus ': ' वजा ',
            ' times ': ' गुणाकार ', ' divided by ': ' भागिले ',
            ' to the power of ': ' घातावर ', ' square root of ': ' वर्गमूळ '
        }
    }
}


def formulas_to_speech(formulas, lang_code, output_path):
    config = LANG_CONFIG.get(lang_code)
    if not config:
        raise ValueError(f"Unsupported language: {lang_code}")

    tts_text = ''
    for i, (name, formula) in enumerate(formulas, 1):
        # identify common
        title = name
        for pat, cname in config['common'].items():
            if re.search(pat.replace(' ', ''), formula.replace(' ', '')):
                title = cname
                break
        # normalize
        eng = normalize_formula(formula)
        # translate symbols
        for e, w in config['translations'].items():
            eng = eng.replace(e, w)
        tts_text += f"{i}. {title}: {eng}\n"

    tts = gTTS(text=tts_text, lang=config['tts_lang'])
    tts.save(output_path)
    return output_path