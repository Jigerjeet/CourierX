📦 CourierX – Tkinter Courier Management System

CourierX is a desktop courier management application built with Python (Tkinter + SQLAlchemy).
It helps you record courier shipments, auto-fill address details using the India Pincode database, generate receipts with QR codes, and even handle UPI payments via QR scanning.

🚀 Features

Tkinter GUI – Simple and modern interface for data entry.
SQLite Database – Stores sender/receiver details, receipts, weight, and payment status.
Auto Address Lookup – Uses India_pincode.csv to auto-fill city, state, and pin code.
UPI Payment QR – Generates a scannable UPI QR for instant payments.
Receipt Generation – Creates a printable receipt with a QR code (tracking info embedded).
Form Placeholders – User-friendly input fields with hints.
Auto Location Detection – Option to fetch sender address/pincode from IP geolocation.

🛠️ Tech Stack

Python 3.10+
Tkinter – GUI framework
SQLAlchemy + SQLite – Database
Pandas – CSV handling (pincode data)
Requests – IP geolocation (auto location)
Pillow (PIL) – Image rendering
qrcode – QR code generation

📂 Project Structure
CourierX/
│── couriers.db             # SQLite database
│── India_pincode.csv       # Pincode dataset (must be present in root)
│── main.py                 # Main Tkinter application
│── README.md               # Documentation
│── requirements.txt        # Python dependencies

⚙️ Installation

Clone or download the project:
git clone https://github.com/yourusername/courierx.git
cd courierx


Install dependencies (preferably inside a virtual environment):
pip install -r requirements.txt



Example requirements

sqlalchemy
pandas
requests
pillow
qrcode



Ensure you have India_pincode.csv in the project root.

▶️ Usage
Run the app:
python main.py



Key Functions:

Fill sender & receiver details.
Auto-fill city/state by typing locality.
Enter weight → auto-calculate delivery price.
Select Payment Method → generates QR (for UPI) or mark as COD.
After submission → Receipt window opens with QR code.

📸 Screenshots (Add yours)

Main Form<img width="1287" height="994" alt="Screenshot 2025-09-13 212047" src="https://github.com/user-attachments/assets/29153129-2353-4936-8a68-b6040d697e34" />

Payment Window<img width="1283" height="996" alt="Screenshot 2025-09-13 212658" src="https://github.com/user-attachments/assets/48bc05d2-31b0-4964-bc4b-62c1374f2c5e" />

Receipt with QR<img width="1226" height="995" alt="Screenshot 2025-09-13 212727" src="https://github.com/user-attachments/assets/e1990c39-060f-48e9-b131-a6e1216a6791" />



👨‍💻 Author
Developed by [Jiger jeet singh]
📧 Email: singhjigerjeet039@gmail.com
