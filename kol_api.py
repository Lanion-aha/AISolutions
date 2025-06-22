from flask import Flask, request, jsonify
import os, json, pandas as pd, matplotlib.pyplot as plt
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
sheets_service = build('sheets', 'v4', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)

INFLUENCER_SPREADSHEET_ID = 'YOUR_SPREADSHEET_ID'
DASHBOARD_FOLDER_ID = 'YOUR_DRIVE_FOLDER_ID'

@app.route("/process", methods=["POST"])
def process_kol():
    row_data = request.json.get("row", [])
    if not row_data or len(row_data) < 6:
        return jsonify({"error": "Invalid data"}), 400

    try:
        pdf_path = generate_pdf(row_data)
        link = upload_to_drive(pdf_path)
        return jsonify({"link": link})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_pdf(row_data, output_path="dashboard.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    keys = ["Timestamp", "Business", "Industry", "Goal", "KOL Type", "Country", "", "", "", "", "", "Email"]
    for k, v in zip(keys, row_data):
        pdf.cell(0, 10, f"{k}: {v}", ln=True)
    pdf.output(output_path)
    return output_path

def upload_to_drive(filepath):
    file_metadata = {"name": os.path.basename(filepath), "parents": [DASHBOARD_FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype='application/pdf')
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded["id"]
    drive_service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/file/d/{file_id}/view"

if __name__ == "__main__":
    app.run(debug=True)
