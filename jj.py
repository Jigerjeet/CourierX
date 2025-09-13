import serial
from datetime import datetime


def print_courier_receipt(data, port='COM3', baudrate=9600):
    """
    Prints a courier delivery receipt via serial thermal printer.

    Parameters:
    - data (dict): Dictionary with keys like 'sender', 'receiver', 'origin', 'destination', 'price', 'payment_mode'
    - port (str): Serial port name (e.g., 'COM3')
    - baudrate (int): Baud rate for the printer (default 9600)
    """

    # Format receipt content
    receipt = f"""
    🏤 Courier Delivery Receipt
    -----------------------------
    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    Sender:      {data.get('sender', 'N/A')}
    Receiver:    {data.get('receiver', 'N/A')}
    Origin:      {data.get('origin', 'N/A')}
    Destination: {data.get('destination', 'N/A')}

    Delivery Fee: ₹{data.get('price', '0.00')}
    Payment Mode: {data.get('payment_mode', 'N/A')}
    -----------------------------
    Thank you for choosing our service!
    \n\n\n
    """

    try:
        # Connect to serial printer
        ser = serial.Serial(port, baudrate, timeout=1)
        ser.write(receipt.encode('utf-8'))
        ser.write(b'\n\n\n')  # Feed paper
        ser.close()
        print("✅ Receipt sent to printer.")
    except Exception as e:
        print(f"❌ Failed to print receipt: {e}")
