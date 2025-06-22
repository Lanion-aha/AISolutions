from flask import Flask, request, jsonify
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

app = Flask(__name__)

# === CẤU HÌNH ===
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
INFLUENCER_SPREADSHEET_ID = '18Pw59giiDPGEF4Z32PxhXljhGsGrhenz4lRoqQBHxxM'
DASHBOARD_FOLDER_ID = '1mc1YjttlTCaG4XwpIuVSnImdWBEh1-YL'

# === GOOGLE API ===
import json

creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
credentials = service_account.Credentials.from_service_account_info(
    creds_info, scopes=SCOPES)

sheets_service = build('sheets', 'v4', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)

@app.route('/process', methods=['POST'])
def process_kol():
    row_data = request.json.get('row', [])
    if not row_data or len(row_data) < 6:
        return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400

    try:
        pdf_path = generate_dashboard_pdf(row_data)
        link = upload_to_drive(pdf_path)
        return jsonify({'link': link})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_dashboard_pdf(row_data, output_path='dashboard.pdf'):
    headers = ['Timestamp', 'Business', 'Industry', 'Goal', 'KOL Type', 'Country', '', '', '', '', '', 'Email']
    data = dict(zip(headers, row_data[:len(headers)]))
    country = str(data.get("Country", "")).strip().lower()
    kol_type = str(data.get("KOL Type", "")).strip().lower().split()[0]

    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=INFLUENCER_SPREADSHEET_ID,
        range="'Data'!A1:Z"
    ).execute()
    rows = result.get('values', [])
    if not rows or len(rows) < 2:
        raise Exception("Không có dữ liệu influencer!")

    df = pd.DataFrame(rows[1:], columns=rows[0])
    df['raw_followers'] = pd.to_numeric(df['raw_followers'], errors='coerce').fillna(0).astype(int)
    df['avgLikes'] = pd.to_numeric(df['avgLikes'], errors='coerce').fillna(0).astype(int)
    df['avgComments'] = pd.to_numeric(df['avgComments'], errors='coerce').fillna(0).astype(int)
    df['engagement'] = df['engagement'].astype(str).str.replace(',', '.').astype(float)
    df['location'] = df['location'].str.replace(r'[\[\]"]', '', regex=True).str.lower().str.strip()
    df['tier'] = df['raw_followers'].apply(lambda x:
        'Nano' if x < 10000 else
        'Micro' if x < 100000 else
        'Macro' if x < 500000 else
        'Mega'
    )

    filtered_df = df.copy()
    if country:
        filtered_df = filtered_df[filtered_df['location'] == country]
    if kol_type and kol_type != 'n/a':
        filtered_df = filtered_df[filtered_df['tier'].str.lower() == kol_type]

    if filtered_df.empty:
        top_df = df.sort_values(by='raw_followers', ascending=False).head(3)
    else:
        filtered_df['score'] = filtered_df['raw_followers'] * 0.6 + filtered_df['engagement'] * 0.4
        top_df = filtered_df.sort_values(by='score', ascending=False).head(3)

    plt.figure(figsize=(6, 4))
    top_df.set_index('username')[['raw_followers', 'avgLikes', 'avgComments']].plot(
        kind='bar', color=['yellow', 'red', 'blue'])
    plt.title("Top 3 Influencers")
    plt.tight_layout()
    chart_path = 'chart.png'
    plt.savefig(chart_path)
    plt.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Influencer Campaign Dashboard", ln=True)
    pdf.set_font("Arial", '', 12)
    for key in ['Business', 'Industry', 'Goal', 'KOL Type', 'Country']:
        pdf.cell(0, 8, f"{key}: {data.get(key, '')}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Top Influencers:", ln=True)
    pdf.set_font("Arial", '', 11)
    for i, row in top_df.iterrows():
        pdf.cell(0, 8, f"{row['username']} - {row['tier']} | {row['raw_followers']} F | {row['avgLikes']} L | {row['avgComments']} C", ln=True)

    pdf.ln(5)
    pdf.image(chart_path, x=10, w=pdf.w - 20)
    pdf.output(output_path)
    return output_path


def upload_to_drive(filepath):
    file_metadata = {'name': os.path.basename(filepath), 'parents': [DASHBOARD_FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype='application/pdf')
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded.get('id')
    drive_service.permissions().create(fileId=file_id, body={'role': 'reader', 'type': 'anyone'}).execute()
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
