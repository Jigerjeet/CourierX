import tkinter as tk
from tkinter import ttk, messagebox, font
import random
import string
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import pandas as pd
import requests
from PIL import Image, ImageTk
import qrcode
import time

# Optional tooltip: idlelib may not be present in packaged environments
try:
    from idlelib.tooltip import Hovertip  # type: ignore
except Exception:
    Hovertip = None  # Fallback: no tooltips

# =========================
# Database
# =========================
Base = declarative_base()
engine = create_engine("sqlite:///couriers.db")
Session = sessionmaker(bind=engine)
session = Session()


class Courier(Base):
    __tablename__ = "couriers"
    id = Column(Integer, primary_key=True)
    receipt = Column(String(20), unique=True)

    sender_name = Column(String(100))
    sender_address = Column(String(300))
    sender_phone = Column(String(20))
    sender_pincode = Column(String(10))

    receiver_name = Column(String(100))
    receiver_address = Column(String(300))
    receiver_phone = Column(String(20))
    receiver_pincode = Column(String(10))

    # New fields we persist
    weight = Column(String(10))
    delivery_price = Column(String(10))
    payment_method = Column(String(30))       # "Google Pay" / "Other UPI App" / "Cash on Delivery"
    payment_status = Column(String(20))       # "Pending" / "Unverified" / "Paid"


Base.metadata.create_all(engine)

# =========================
# Pincode CSV load (cached)
# =========================
PINCODES_DF = None
COL_AREA = COL_PIN = COL_DIST = COL_STATE = None


def load_pincode_csv():
    """Load India_pincode.csv with flexible column detection."""
    global PINCODES_DF, COL_AREA, COL_PIN, COL_DIST, COL_STATE
    try:
        PINCODES_DF = pd.read_csv("India_pincode.csv", low_memory=False)
        PINCODES_DF.columns = [c.strip() for c in PINCODES_DF.columns]

        def find_col(candidates):
            cols_norm = {c: c.strip().lower().replace(" ", "").replace("_", "") for c in PINCODES_DF.columns}
            for c, n in cols_norm.items():
                if n in candidates:
                    return c
            return None

        # Try common variants
        COL_AREA = find_col({"area", "locality", "officename", "village", "location", "place", "areaname"})
        COL_PIN = find_col({"pincode", "pin", "postcode", "zipcode", "pincodeno", "pincodenumber"})
        if COL_PIN is None:
            for c in PINCODES_DF.columns:
                if c.strip().lower() in ("pin code", "pin-code", "pin code number", "p.o.pincode"):
                    COL_PIN = c
                    break

        # District / City
        for c in PINCODES_DF.columns:
            if c.strip().lower() in ("district"):
                COL_DIST = c
                break

        # State
        for c in PINCODES_DF.columns:
            if c.strip().lower() in ("state", "statename"):
                COL_STATE = c
                break
    except Exception as e:
        print(f"[WARN] Failed to load India_pincode.csv: {e}")


load_pincode_csv()

# =========================
# Helpers
# =========================

# ---------- Placeholder helpers (with state) ----------
def _mark_placeholder(entry: ttk.Entry, text: str):
    entry._has_placeholder = True
    entry._placeholder_text = text
    entry.configure(validate="none")
    entry.delete(0, tk.END)
    entry.insert(0, text)
    entry.configure(foreground="gray")
    entry.configure(validate="key")


def _clear_placeholder(entry: ttk.Entry):
    entry._has_placeholder = False
    entry.configure(foreground="black")


def add_placeholder(entry: ttk.Entry, placeholder_text: str):
    entry._has_placeholder = False
    entry._placeholder_text = placeholder_text

    def on_focus_in(_):
        if getattr(entry, "_has_placeholder", False) and entry.get() == entry._placeholder_text:
            entry.configure(validate="none")
            entry.delete(0, tk.END)
            _clear_placeholder(entry)
            entry.configure(validate="key")

    def on_focus_out(_):
        if entry.get() == "":
            _mark_placeholder(entry, placeholder_text)

    if entry.get() == "":
        _mark_placeholder(entry, placeholder_text)

    entry.bind("<FocusIn>", on_focus_in, add="+")
    entry.bind("<FocusOut>", on_focus_out, add="+")


def set_entry_text(entry: ttk.Entry, text: str):
    entry.configure(validate="none")
    entry.delete(0, tk.END)
    entry.insert(0, text)
    entry.configure(validate="key")
    _clear_placeholder(entry)


def get_value(entry: ttk.Entry) -> str:
    """Return entry text while ignoring placeholder text."""
    txt = entry.get().strip()
    if getattr(entry, "_has_placeholder", False) and txt == getattr(entry, "_placeholder_text", ""):
        return ""
    return txt


def get_current_location():
    """Fill sender address and pincode using IP geolocation (best-effort)."""
    set_entry_text(entry_sender_address, "")
    set_entry_text(entry_pincode_sender, "")
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=4)
        data = resp.json()
        city = data.get("city", "") or ""
        state = data.get("region", "") or ""
        pincode = data.get("postal", "") or ""
        loc = f"{city}, {state}".strip(", ")
        set_entry_text(entry_sender_address, loc)
        set_entry_text(entry_pincode_sender, pincode)
    except Exception as e:
        messagebox.showwarning("Location", f"Couldn't fetch location automatically.\n{e}")


def validate_phone(P: str) -> bool:
    return P == "" or (P.isdigit() and len(P) <= 10)


def phn_is_valid(number: str) -> bool:
    return number.isdigit() and len(number) == 10 and number[0] in "6789"


def validate_pincode(P: str) -> bool:
    return P == "" or (P.isdigit() and len(P) <= 6)


def normalize_pin_value(val) -> str:
    s = str(val).strip()
    if "." in s:  # CSV sometimes has floats
        s = s.split(".", 1)[0]
    return s


def info_sender(area: str):
    """Lookup sender pincode by area name."""
    set_entry_text(entry_pincode_sender, "")
    if PINCODES_DF is None or not COL_AREA or not COL_PIN:
        messagebox.showinfo("Not Found", "Pincode data not loaded or columns missing.")
        return
    area = (area or "").strip().lower()
    matched_rows = PINCODES_DF[PINCODES_DF[COL_AREA].fillna("").str.strip().str.lower() == area]
    if not matched_rows.empty:
        pincode1 = normalize_pin_value(matched_rows.iloc[0][COL_PIN])
        set_entry_text(entry_pincode_sender, pincode1)
    else:
        messagebox.showinfo("Not Found", f"No match found for sender area: {area}")


def info_receiver(area: str):
    set_entry_text(entry_city, "")
    set_entry_text(entry_state, "")
    set_entry_text(entry_pincode, "")
    if PINCODES_DF is None or not COL_AREA or not COL_PIN:
        messagebox.showinfo("Not Found", "Pincode data not loaded or columns missing.")
        return
    area = (area or "").strip().lower()
    matched_rows = PINCODES_DF[PINCODES_DF[COL_AREA].fillna("").str.strip().str.lower() == area]
    if not matched_rows.empty:
        row = matched_rows.iloc[0]
        if COL_DIST:
            set_entry_text(entry_city, str(row[COL_DIST]).strip())
        if COL_STATE:
            set_entry_text(entry_state, str(row[COL_STATE]).strip())
        set_entry_text(entry_pincode, normalize_pin_value(row[COL_PIN]))
    else:
        messagebox.showinfo("Not Found", f"No match found for receiver area: {area}")


def calculate_delivery_price(state: str, weight: float) -> float:
    state = (state or "").strip().lower()
    preferred_states = {"haryana", "punjab", "uttar pradesh", "delhi", "rajasthan", "himachal pradesh"}
    state_aliases = {"up": "uttar pradesh", "hp": "himachal pradesh"}
    state = state_aliases.get(state, state)
    rate = 70 if state in preferred_states else 120
    return round(rate * float(weight), 2)


def generate_receipt(prefix: str = "EM", length: int = 10) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        random_part = ''.join(random.choices(chars, k=length - len(prefix)))
        rcpt = prefix + random_part
        existing = session.query(Courier).filter_by(receipt=rcpt).first()
        if not existing:
            return rcpt


def payment(amount_float):
    """Open a QR payment window for UPI."""
    upi_id = "jigerjeet@upi"
    payee_name = "Jigerjeet"
    note = "Courier Payment"

    try:
        amount = float(amount_float)
    except Exception:
        amount = 0.0

    upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount:.2f}&cu=INR&tn={note}"
    qr_img = qrcode.make(upi_url)

    root_payment = tk.Toplevel(root)
    root_payment.title("UPI Payment - Courier Checkout")
    root_payment.geometry("350x500")
    root_payment.configure(bg="#f0f4f7")

    title_font = ("Helvetica", 14, "bold")
    label_font = ("Helvetica", 10)
    timer_font = ("Helvetica", 12, "bold")

    tk.Label(root_payment, text="Scan to Pay", font=title_font, bg="#f0f4f7", fg="#333").pack(pady=(20, 5))
    tk.Label(root_payment, text=f"Pay ₹{amount:.2f} to {payee_name}", font=label_font, bg="#f0f4f7", fg="#555").pack(
        pady=(0, 10))

    qr_img_resized = qr_img.resize((200, 200))
    qr_photo = ImageTk.PhotoImage(qr_img_resized)
    qr_label = tk.Label(root_payment, image=qr_photo, bg="#f0f4f7")
    qr_label.image = qr_photo
    qr_label.pack(pady=10)

    timer_label = tk.Label(root_payment, text="", font=timer_font, fg="red", bg="#f0f4f7")
    timer_label.pack(pady=(5, 10))

    time_left = [10 * 60]

    def update_timer():
        if time_left[0] > 0:
            mins, secs = divmod(time_left[0], 60)
            timer_label.config(text=f"Time left: {mins:02d}:{secs:02d}")
            time_left[0] -= 1
            root_payment.after(1000, update_timer)
        else:
            timer_label.config(text="Time expired")
            root_payment.after(3000, root_payment.destroy)

    update_timer()

    tk.Label(root_payment, text=f"Note: {note}", font=label_font, bg="#f0f4f7", fg="#777").pack(pady=(5, 20))
    tk.Button(root_payment, text="← Back", width=10, bg="#d7ccc8", fg="#4e342e",
              command=root_payment.destroy).pack()


def clear_form():
    for entry in [
        entry_sender_name, entry_sender_address, entry_pincode_sender, entry_sender_phone,
        entry_receiver_name, entry_house, entry_street, entry_locality,
        entry_city, entry_state, entry_pincode, entry_receiver_phone, entry_weight
    ]:
        entry.delete(0, tk.END)
    add()
    status_var.set("Form cleared")


def receipt_wind():
    """Show receipt window based on the last 'receipt' global."""
    try:
        c = session.query(Courier).filter_by(receipt=receipt).one()
    except Exception as e:
        messagebox.showerror("Error", f"Could not load receipt data:\n{e}")
        return

    receipt_window = tk.Toplevel(root)
    receipt_window.title("Courier Receipt")
    receipt_window.geometry("820x680")
    receipt_window.configure(bg="#f5f5f5")

    tk.Label(receipt_window, text="✅ Courier Submitted Successfully!",
             font=("Helvetica", 16, "bold"), fg="#4CAF50", bg="#f5f5f5").pack(pady=10)

    tk.Label(receipt_window, text=f"Receipt No: {c.receipt}",
             font=("Helvetica", 12), bg="#f5f5f5").pack(pady=5)

    info_frame = tk.Frame(receipt_window, bg="#f5f5f5")
    info_frame.pack(pady=10, fill="x", padx=40)

    sender_frame = tk.Frame(info_frame, bg="#f5f5f5")
    sender_frame.pack(side=tk.LEFT, anchor="n", expand=True, fill="both", padx=(0, 10))

    tk.Label(sender_frame, text="📤 Sender Details", font=("Helvetica", 14, "bold"), bg="#f5f5f5").pack(anchor="w", pady=(0, 5))
    for text in [
        f"Name: {c.sender_name}",
        f"Address: {c.sender_address}",
        f"Phone: {c.sender_phone}",
        f"Pin Code: {c.sender_pincode}",
    ]:
        tk.Label(sender_frame, text=text, font=("Helvetica", 12), bg="#f5f5f5").pack(anchor="w")

    receiver_frame = tk.Frame(info_frame, bg="#f5f5f5")
    receiver_frame.pack(side=tk.RIGHT, anchor="n", expand=True, fill="both", padx=(10, 0))

    tk.Label(receiver_frame, text="📥 Receiver Details", font=("Helvetica", 14, "bold"), bg="#f5f5f5").pack(anchor="e", pady=(0, 5))
    for text in [
        f"Name: {c.receiver_name}",
        f"Address: {c.receiver_address}",
        f"Phone: {c.receiver_phone}",
        f"Pin Code: {c.receiver_pincode}",
    ]:
        tk.Label(receiver_frame, text=text, font=("Helvetica", 12), bg="#f5f5f5").pack(anchor="e")



    # Payment info
    pay_text = f"Payment Method: {c.payment_method or '—'}"
    status_text = f"Payment Status: {c.payment_status or 'Pending'}"
    tk.Label(receipt_window, text=pay_text, font=("Helvetica", 12), bg="#f5f5f5").pack()
    tk.Label(receipt_window, text=status_text, font=("Helvetica", 12), bg="#f5f5f5").pack(pady=(0, 8))

    # Receipt QR (info)
    tk.Label(receipt_window, text="📄 Receipt QR Code",
             font=("Helvetica", 14, "bold"), bg="#f5f5f5", fg="#333").pack(pady=(20, 5))

    qr_data = (
        f"Receipt: {c.receipt}\n"
        f"Sender: {c.sender_name}, {c.sender_phone}, {c.sender_pincode}\n"
        f"Receiver: {c.receiver_name}, {c.receiver_phone}, {c.receiver_pincode}\n"
        f"Weight: {c.weight} kg\n"
        f"Delivery Price: ₹{c.delivery_price}\n"
        f"Payment: {c.payment_method or '—'} ({c.payment_status or 'Pending'})\n"
        f"Status: Submitted"
    )
    qr_img = qrcode.make(qr_data).resize((180, 180))
    qr_photo = ImageTk.PhotoImage(qr_img)

    qr_frame = tk.Frame(receipt_window, bg="white", bd=2, relief="groove")
    qr_label = tk.Label(qr_frame, image=qr_photo, bg="white")
    qr_label.image = qr_photo
    qr_label.pack()
    qr_frame.pack(pady=10)

    def save_qr():
        try:
            fname = f"{c.receipt}_qr.png"
            qr_img.save(fname)
            messagebox.showinfo("Saved", f"QR Code saved as {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't save QR code:\n{e}")

    def print_qr():
        try:
            qr_img.show()
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't open the image viewer:\n{e}")

    btn_frame = tk.Frame(receipt_window, bg="#f5f5f5")
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="💾 Save QR Code", font=("Helvetica", 12), bg="#2196F3", fg="white",
              command=save_qr).pack(side=tk.LEFT, padx=10)

    tk.Button(btn_frame, text="🖨️ Print", font=("Helvetica", 12), bg="#4CAF50", fg="white",
              command=print_qr).pack(side=tk.LEFT, padx=10)

    tk.Button(btn_frame, text="❌ Close Receipt", font=("Helvetica", 12), bg="#f44336", fg="white",
              command=receipt_window.destroy).pack(side=tk.LEFT, padx=10)

    clear_form()


def submit():
    global receipt  # used by receipt_wind()

    # Read values while stripping placeholders
    sender_name = get_value(entry_sender_name)
    sender_address = get_value(entry_sender_address)
    sender_pincode = get_value(entry_pincode_sender)
    sender_phone = get_value(entry_sender_phone)

    receiver_name = get_value(entry_receiver_name)
    house = get_value(entry_house)
    street = get_value(entry_street)
    locality = get_value(entry_locality)
    city = get_value(entry_city)
    state = get_value(entry_state)
    receiver_pincode = get_value(entry_pincode)
    receiver_phone = get_value(entry_receiver_phone)

    weight = get_value(entry_weight)

    # Validation
    if not all([sender_name, sender_address, sender_pincode, sender_phone]):
        messagebox.showwarning("Missing Info", "Please fill in all sender details.")
        return
    if not all([receiver_name, street, locality, city, state, receiver_pincode, receiver_phone]):
        messagebox.showwarning("Missing Info", "Please fill in all receiver details.")
        return
    if not phn_is_valid(sender_phone):
        messagebox.showwarning("Invalid Phone", "Sender phone must be 10 digits and start with 6, 7, 8, or 9.")
        return
    if not phn_is_valid(receiver_phone):
        messagebox.showwarning("Invalid Phone", "Receiver phone must be 10 digits and start with 6, 7, 8, or 9.")
        return
    if not (sender_pincode.isdigit() and len(sender_pincode) == 6):
        messagebox.showwarning("Invalid PIN", "Sender PIN must be exactly 6 digits.")
        return
    if not (receiver_pincode.isdigit() and len(receiver_pincode) == 6):
        messagebox.showwarning("Invalid PIN", "Receiver PIN must be exactly 6 digits.")
        return
    if not weight:
        messagebox.showwarning("Missing Info", "Please enter package weight (kg).")
        return
    try:
        weight_float = float(weight)
        if weight_float <= 0:
            raise ValueError
    except Exception:
        messagebox.showwarning("Invalid Weight", "Weight must be a positive number, e.g., 2.5")
        return

    receiver_address = f"{house}, {street}, {locality}, {city}, {state}"
    receipt = generate_receipt()

    info = (
        f"Receipt No: {receipt}\n\n"
        f"Sender Info:\n"
        f"Name: {sender_name}\n"
        f"Address: {sender_address}\n"
        f"Phone: {sender_phone}\n"
        f"Pin Code: {sender_pincode}\n\n"
        f"Receiver Info:\n"
        f"Name: {receiver_name}\n"
        f"Address: {receiver_address}\n"
        f"Phone: {receiver_phone}\n"
        f"Pin Code: {receiver_pincode}\n\n"
        f"Package:\n"
        f"Weight: {weight_float} kg"
    )
    if not messagebox.askokcancel("Confirm Submission", info):
        return

    # Compute delivery price BEFORE insert so we save it
    AM = calculate_delivery_price(state, weight_float)

    # Insert into DB
    new_courier = Courier(
        receipt=receipt,
        sender_name=sender_name,
        sender_address=sender_address,
        sender_phone=sender_phone,
        sender_pincode=sender_pincode,
        receiver_name=receiver_name,
        receiver_address=receiver_address,
        receiver_phone=receiver_phone,
        receiver_pincode=receiver_pincode,
        weight=f"{weight_float}",
        delivery_price=f"{AM:.2f}",
        payment_method=None,
        payment_status="Pending",
    )
    session.add(new_courier)
    session.commit()

    # Checkout window (use Toplevel, not another Tk)
    root2 = tk.Toplevel(root)
    root2.geometry("860x760")
    root2.title(f"Courier Checkout - {receiver_name}")
    root2.configure(bg="#f0f4f7")

    title_font = font.Font(family="Helvetica", size=16, weight="bold")
    label_font = font.Font(family="Helvetica", size=11)

    delivery_price_var = tk.StringVar(value=f"₹{AM:.2f}")

    tk.Label(root2, text=f"Delivering to {receiver_name}", font=title_font, bg="#f0f4f7", fg="#222").pack(pady=(20, 5))
    tk.Label(root2, text=f"Address:{receiver_address}", font=label_font, bg="#f0f4f7", fg="#555").pack()

    # Price
    tk.Label(root2, textvariable=delivery_price_var, font=("Helvetica", 18, "bold"),
             bg="#f0f4f7", fg="#007f5f").pack(pady=(5, 20))

    # Separator
    tk.Frame(root2, height=2, bd=0, bg="#ccc").pack(fill="x", padx=30, pady=10)

    # Payment options frame
    payment_frame = tk.LabelFrame(root2, text="Choose Payment Method", bg="#f0f4f7", fg="#333",
                                  font=label_font, padx=15, pady=15)
    payment_frame.pack(padx=30, pady=10, fill="x")

    selected_payment = tk.StringVar(value="")

    def choose_payment(method: str, open_qr: bool = False):
        selected_payment.set(method)
        try:
            c = session.query(Courier).filter_by(receipt=receipt).one()
            c.payment_method = method
            c.delivery_price = f"{AM:.2f}"
            c.payment_status = "Pending" if method == "Cash on Delivery" else "Unverified"
            session.commit()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save payment method:\n{e}")
            return

        if open_qr:
            payment(AM)
        if method == "Cash on Delivery":
            receipt_wind()  # Show receipt directly for COD

    def create_payment_button(text, bg, fg, command=None):
        btn = tk.Button(payment_frame, text=text, width=25, bg=bg, fg=fg,
                        relief="flat", font=label_font, pady=8, command=command)
        btn.pack(pady=8)

        def on_enter(_): btn.config(bg="#b2ebf2")
        def on_leave(_): btn.config(bg=bg)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    create_payment_button(
        "Google Pay", "#e0f7fa", "#00796b",
        command=lambda: choose_payment("Google Pay", open_qr=True)
    )
    create_payment_button(
        "Other UPI App", "#e0f7fa", "#00796b",
        command=lambda: choose_payment("Other UPI App", open_qr=True)
    )
    create_payment_button(
        "Cash on Delivery", "#ffe0b2", "#bf360c",
        command=lambda: choose_payment("Cash on Delivery", open_qr=False)
    )

    tk.Button(root2, text="← Back", width=10, bg="#d7ccc8", fg="#4e342e", font=label_font,
              command=root2.destroy).place(x=30, y=20)

# =========================
# Tkinter GUI
# =========================
root = tk.Tk()
root.geometry("860x760")
root.title("CourierX")
root.configure(bg="#F5F5F5")

LABEL_FONT = ("Helvetica", 12)
HEADER_FONT = ("Helvetica", 14, "bold")

style = ttk.Style()
style.configure("TLabel", background="#F5F5F5", font=LABEL_FONT)
style.configure("TButton", font=LABEL_FONT, padding=6)
style.configure("TEntry", padding=4)
style.configure("TLabelframe.Label", font=HEADER_FONT)

status_var = tk.StringVar(value="Ready")
status_bar = ttk.Label(root, textvariable=status_var, relief="sunken", anchor="w")
status_bar.pack(fill="x", side="bottom")

phone_vcmd = (root.register(validate_phone), '%P')
pincode_vcmd = (root.register(validate_pincode), '%P')

def validate_name(P: str) -> bool:
    return P == "" or (len(P) <= 30 and all(c.isalpha() or c.isspace() for c in P))

name_vcmd = (root.register(validate_name), '%P')

# Package Details
package_frame = ttk.LabelFrame(root, text="📦 Package Details", padding=10)
package_frame.pack(fill="x", padx=20, pady=10)

ttk.Label(package_frame, text="Weight (kg):").grid(row=0, column=0, sticky="w", pady=5)
entry_weight = ttk.Entry(package_frame, width=30)
entry_weight.grid(row=0, column=1, pady=5)
if Hovertip:
    Hovertip(entry_weight, "Enter weight in kilograms")

# Sender Info
sender_frame = ttk.LabelFrame(root, text="📍 Sender Information", padding=10)
sender_frame.pack(fill="x", padx=20, pady=10)

ttk.Label(sender_frame, text="Full Name:").grid(row=0, column=0, sticky="w", pady=5)
entry_sender_name = ttk.Entry(sender_frame, width=30, validate="key", validatecommand=name_vcmd)
entry_sender_name.grid(row=0, column=1, pady=5)

ttk.Label(sender_frame, text="Address:").grid(row=1, column=0, sticky="w", pady=5)
entry_sender_address = ttk.Entry(sender_frame, width=30)
entry_sender_address.grid(row=1, column=1, pady=5)

ttk.Label(sender_frame, text="Pin Code:").grid(row=1, column=2, sticky="w", pady=5)
entry_pincode_sender = ttk.Entry(sender_frame, width=30, validate="key", validatecommand=pincode_vcmd)
entry_pincode_sender.grid(row=1, column=3, pady=5)

ttk.Label(sender_frame, text="Phone Number:").grid(row=2, column=0, sticky="w", pady=5)
entry_sender_phone = ttk.Entry(sender_frame, width=30, validate="key", validatecommand=phone_vcmd)
entry_sender_phone.grid(row=2, column=1, pady=5)

btn_auto_location = ttk.Button(sender_frame, text="Auto Location", command=get_current_location)
btn_auto_location.grid(row=2, column=3, pady=5)

# Separator
ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=5)

# Receiver Info
receiver_frame = ttk.LabelFrame(root, text="📦 Receiver Information", padding=10)
receiver_frame.pack(fill="x", padx=20, pady=10)

ttk.Label(receiver_frame, text="Full Name:").grid(row=0, column=0, sticky="w", pady=5)
entry_receiver_name = ttk.Entry(receiver_frame, width=30, validate="key", validatecommand=name_vcmd)
entry_receiver_name.grid(row=0, column=1, pady=5)

ttk.Label(receiver_frame, text="House/Flat No.:").grid(row=0, column=2, sticky="w", pady=5)
entry_house = ttk.Entry(receiver_frame, width=30)
entry_house.grid(row=0, column=3, pady=5)

ttk.Label(receiver_frame, text="Street Name:").grid(row=1, column=0, sticky="w", pady=5)
entry_street = ttk.Entry(receiver_frame, width=30)
entry_street.grid(row=1, column=1, pady=5)

ttk.Label(receiver_frame, text="Locality/Area:").grid(row=1, column=2, sticky="w", pady=5)
entry_locality = ttk.Entry(receiver_frame, width=30)
entry_locality.grid(row=1, column=3, pady=5)

# Auto-fill district/state/pin when locality loses focus (only if not placeholder)
def on_locality_focus_out(_):
    if not getattr(entry_locality, "_has_placeholder", False):
        info_receiver(entry_locality.get())

entry_locality.bind("<FocusOut>", on_locality_focus_out, add="+")

ttk.Label(receiver_frame, text="City (District):").grid(row=2, column=0, sticky="w", pady=5)
entry_city = ttk.Entry(receiver_frame, width=30)
entry_city.grid(row=2, column=1, pady=5)

ttk.Label(receiver_frame, text="State:").grid(row=2, column=2, sticky="w", pady=5)
entry_state = ttk.Entry(receiver_frame, width=30)
entry_state.grid(row=2, column=3, pady=5)

ttk.Label(receiver_frame, text="Pin Code:").grid(row=3, column=0, sticky="w", pady=5)
entry_pincode = ttk.Entry(receiver_frame, width=30, validate="key", validatecommand=pincode_vcmd)
entry_pincode.grid(row=3, column=1, pady=5)

ttk.Label(receiver_frame, text="Phone Number:").grid(row=3, column=2, sticky="w", pady=5)
entry_receiver_phone = ttk.Entry(receiver_frame, width=30, validate="key", validatecommand=phone_vcmd)
entry_receiver_phone.grid(row=3, column=3, pady=5)

# Buttons
button_frame = ttk.Frame(root)
button_frame.pack(pady=12)

submit_btn = ttk.Button(button_frame, text="Submit", command=submit)
submit_btn.pack(side="left", padx=10)

clear_btn = ttk.Button(button_frame, text="Clear Form", command=clear_form)
clear_btn.pack(side="left", padx=10)



def add():
    add_placeholder(entry_sender_name, "Enter sender's full name")
    add_placeholder(entry_sender_address, "Street, City, State")
    add_placeholder(entry_pincode_sender, "6-digit PIN")
    add_placeholder(entry_sender_phone, "10-digit mobile number")

    add_placeholder(entry_receiver_name, "Enter receiver's full name")
    add_placeholder(entry_house, "House/Flat No.")
    add_placeholder(entry_street, "Street Name")
    add_placeholder(entry_locality, "Locality or Area")
    add_placeholder(entry_city, "City or District")
    add_placeholder(entry_state, "State")
    add_placeholder(entry_pincode, "6-digit PIN")
    add_placeholder(entry_receiver_phone, "10-digit mobile number")
    add_placeholder(entry_weight, "e.g. 2.5")

# Initialize placeholders
add()

if __name__ == "__main__":
    root.mainloop()
