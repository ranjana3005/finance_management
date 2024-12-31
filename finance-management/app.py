from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pass",
    database="financemanagement"
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
        db.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/balances', methods=['GET', 'POST'])
def balances():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        card_number = request.form['card_number']
        card_name = request.form['card_name']
        expiry_date = request.form['expiry_date']
        cvv = request.form['cvv']
        amount = float(request.form['amount'])
        
        cursor.execute(
            "INSERT INTO account (user_id, card_number, card_name, expiry_date, cvv, balance) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user_id'], card_number, card_name, expiry_date, cvv, amount)
        )
        db.commit()
        flash('Account added successfully!', 'success')
        return redirect(url_for('balances'))
    cursor.execute("SELECT * FROM account WHERE user_id = %s", (session['user_id'],))
    accounts = cursor.fetchall()
    
    return render_template('balances.html', accounts=accounts)


@app.route('/bills', methods=['GET', 'POST'])
def bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    # Handle adding new bill
    if request.method == 'POST' and 'name' in request.form:
        name = request.form['name']
        description = request.form['description']
        due_date = request.form['due_date']
        amount = float(request.form['amount'])
        
        cursor.execute("INSERT INTO bills (user_id, bill_name, amount, due_date, status, paid) VALUES (%s, %s, %s, %s, %s, %s)",
                       (session['user_id'], name, amount, due_date, 'Pending', 0))
        db.commit()
        flash('Bill added successfully!', 'success')
        return redirect(url_for('bills'))
    
    # Fetch user's bills and accounts
    cursor.execute("SELECT * FROM bills WHERE user_id = %s", (session['user_id'],))
    bills = cursor.fetchall()
    
    cursor.execute("SELECT * FROM account WHERE user_id = %s", (session['user_id'],))
    accounts = cursor.fetchall()

    current_date = datetime.now().date()
    due_alerts = [bill for bill in bills if bill.get('due_date') <= current_date and bill.get('status') != 'Paid']

    return render_template('bills.html', bills=bills, due_alerts=due_alerts, accounts=accounts)

@app.route('/pay_bill/<int:bill_id>', methods=['POST'])
def pay_bill(bill_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    # Fetch the bill to be paid
    cursor.execute("SELECT * FROM bills WHERE id = %s AND user_id = %s", (bill_id, session['user_id']))
    bill = cursor.fetchone()
    
    if not bill:
        flash('Bill not found!', 'danger')
        return redirect(url_for('bills'))
    
    if bill['paid']:
        flash('Bill already paid!', 'warning')
        return redirect(url_for('bills'))
    
    # Get the selected account for payment
    account_id = request.form['account']
    
    cursor.execute("SELECT * FROM account WHERE id = %s AND user_id = %s", (account_id, session['user_id']))
    account = cursor.fetchone()
    
    if not account:
        flash('Account not found!', 'danger')
        return redirect(url_for('bills'))
    
    if account['balance'] < bill['amount']:
        flash('Insufficient balance to pay the bill!', 'danger')
        return redirect(url_for('bills'))
    
    # Deduct the bill amount from the selected account balance
    new_balance = account['balance'] - bill['amount']
    cursor.execute("UPDATE account SET balance = %s WHERE id = %s", (new_balance, account_id))
    
    # Mark the bill as paid
    cursor.execute("UPDATE bills SET paid = %s WHERE id = %s", (True, bill_id))
    
    # Log the transaction
    cursor.execute(
        "INSERT INTO transactions (user_id, item, account_name, date_of_payment, payment_type, amount) VALUES (%s, %s, %s, %s, %s, %s)",
        (session['user_id'], bill['name'], account['card_name'], datetime.now().date(), 'Withdraw', bill['amount'])
    )
    
    db.commit()
    flash('Bill paid successfully!', 'success')
    return redirect(url_for('bills'))

@app.route('/expenses', methods=['GET'])
def expenses():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    # Retrieve all transactions to categorize into credits and debits
    cursor.execute("SELECT payment_type, SUM(amount) as total FROM transactions WHERE user_id = %s GROUP BY payment_type", (session['user_id'],))
    summary = cursor.fetchall()
    
    credits = next((item['total'] for item in summary if item['payment_type'] == 'Deposit'), 0)
    debits = next((item['total'] for item in summary if item['payment_type'] == 'Withdraw'), 0)
    
    return render_template('expenses.html', credits=credits, debits=debits)

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        goal_name = request.form['goal_name']
        target_amount = float(request.form['target_amount'])
        
        cursor.execute(
            "INSERT INTO goals (user_id, goal_name, target_amount, saved_amount) VALUES (%s, %s, %s, %s)",
            (session['user_id'], goal_name, target_amount, 0.00)
        )
        db.commit()
        flash('Goal added successfully!', 'success')
        return redirect(url_for('goals'))
    
    cursor.execute("SELECT * FROM goals WHERE user_id = %s", (session['user_id'],))
    goals = cursor.fetchall()
    
    return render_template('goals.html', goals=goals)

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)

    # Total Account Balance
    cursor.execute("SELECT SUM(balance) as total_balance FROM account WHERE user_id = %s", (session['user_id'],))
    balance_row = cursor.fetchone()
    total_balance = balance_row['total_balance'] if balance_row and balance_row['total_balance'] else 0.0

    # Last Five Transactions
    cursor.execute("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC LIMIT 5", (session['user_id'],))
    transactions = cursor.fetchall()

    # Pending Bills
    cursor.execute("SELECT * FROM bills WHERE user_id = %s AND paid = 0", (session['user_id'],))
    pending_bills = cursor.fetchall()

    # Expense Summary for Graph
    cursor.execute("""
        SELECT payment_type, SUM(amount) as total
        FROM transactions 
        WHERE user_id = %s 
        GROUP BY payment_type
    """, (session['user_id'],))
    expense_data = cursor.fetchall()
    
    credits = next((item['total'] for item in expense_data if item['payment_type'] == 'Deposit'), 0)
    debits = next((item['total'] for item in expense_data if item['payment_type'] == 'Withdraw'), 0)
    
    return render_template(
        'dashboard.html',
        username=session['user_name'],
        total_balance=total_balance,
        transactions=transactions,
        pending_bills=pending_bills,
        credits=credits,
        debits=debits
    )

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        item = request.form['item']
        account_name = request.form['account_name']
        date_of_payment = request.form['date_of_payment']
        payment_type = request.form['payment_type']
        amount = float(request.form['amount'])

        cursor.execute(
            "INSERT INTO transactions (user_id, item, account_name, date_of_payment, payment_type, amount) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user_id'], item, account_name, date_of_payment, payment_type, amount)
        )

        cursor.execute("SELECT balance FROM account WHERE card_name = %s AND user_id = %s", (account_name, session['user_id']))
        balance_row = cursor.fetchone()

        if not balance_row:
            flash('Account not found!', 'danger')
            db.rollback()
            return redirect(url_for('transactions'))
        
        balance = balance_row['balance']

        if payment_type == 'Withdraw' and balance >= amount:
            cursor.execute("UPDATE account SET balance = balance - %s WHERE card_name = %s AND user_id = %s", (amount, account_name, session['user_id']))
        elif payment_type == 'Deposit':
            cursor.execute("UPDATE account SET balance = balance + %s WHERE card_name = %s AND user_id = %s", (amount, account_name, session['user_id']))
        else:
            flash('Insufficient balance for withdrawal!', 'danger')
            db.rollback()
            return redirect(url_for('transactions'))

        db.commit()
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions'))

    cursor.execute("SELECT * FROM account WHERE user_id = %s", (session['user_id'],))
    accounts = cursor.fetchall()

    cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (session['user_id'],))
    transaction_list = cursor.fetchall()

    cursor.execute("SELECT SUM(balance) as total_balance FROM account WHERE user_id = %s", (session['user_id'],))
    balance_row = cursor.fetchone()
    total_balance = balance_row['total_balance'] if balance_row and balance_row['total_balance'] else 0.0

    return render_template('transactions.html', accounts=accounts, transactions=transaction_list, balance=total_balance)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)




'''
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pass",
    database="financemanagement"
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
        db.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['user_name'])

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        item = request.form['item']
        goal = request.form['goal']
        account_name = request.form['account_name']
        date_of_payment = request.form['date_of_payment']
        payment_type = request.form['payment_type']
        amount = float(request.form['amount'])

        # Insert the transaction
        cursor.execute("INSERT INTO transactions (user_id, item, goal, account_name, date_of_payment, payment_type, amount) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                       (session['user_id'], item, goal, account_name, date_of_payment, payment_type, amount))

        # Check if account exists for the user
        cursor.execute("SELECT balance FROM account WHERE user_id = %s", (session['user_id'],))
        balance_row = cursor.fetchone()

        if not balance_row:
            # If no account exists, create an account with initial balance 0
            cursor.execute("INSERT INTO account (user_id, balance) VALUES (%s, 0)", (session['user_id'],))
            db.commit()
            balance = 0
        else:
            balance = balance_row['balance']

        if payment_type == 'Withdraw' and balance >= amount:
            # If it's a withdrawal and balance is sufficient
            cursor.execute("UPDATE account SET balance = balance - %s WHERE user_id = %s", (amount, session['user_id']))
        elif payment_type == 'Deposit':
            # If it's a deposit
            cursor.execute("UPDATE account SET balance = balance + %s WHERE user_id = %s", (amount, session['user_id']))
        else:
            flash('Insufficient balance for withdrawal!', 'danger')
            db.rollback()
            return redirect(url_for('transactions'))

        db.commit()
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions'))

    # Retrieve current balance
    cursor.execute("SELECT balance FROM account WHERE user_id = %s", (session['user_id'],))
    balance_row = cursor.fetchone()
    balance = balance_row['balance'] if balance_row else 0

    # Retrieve transactions
    cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (session['user_id'],))
    transaction_list = cursor.fetchall()

    return render_template('transactions.html', balance=balance, transactions=transaction_list)

@app.route('/bills', methods=['GET', 'POST'])
def bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    # Handle the POST request for adding a new bill
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        due_date = request.form['due_date']
        amount = float(request.form['amount'])
        
        # Insert the new bill into the database
        cursor.execute("INSERT INTO bills (user_id, name, description, due_date, amount) VALUES (%s, %s, %s, %s, %s)",
                       (session['user_id'], name, description, due_date, amount))
        db.commit()
        flash('Bill added successfully!', 'success')
        return redirect(url_for('bills'))
    
    # Retrieve all bills for the current user
    cursor.execute("SELECT * FROM bills WHERE user_id = %s", (session['user_id'],))
    bills = cursor.fetchall()

    # Check for overdue bills
    current_date = datetime.now().date()
    due_alerts = [bill for bill in bills if bill['due_date'] <= current_date]
    
    return render_template('bills.html', bills=bills, due_alerts=due_alerts)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
'''
'''
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pass",
    database="financemanagement"
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
        db.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['user_name'])

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cursor = db.cursor()
    if request.method == 'POST':
        transaction_type = request.form['type']
        amount = float(request.form['amount'])
        cursor.execute("SELECT balance FROM account WHERE user_id = %s", (session['user_id'],))
        balance_row = cursor.fetchone()
        balance = balance_row[0] if balance_row else 0
        if transaction_type == 'Deposit':
            cursor.execute("UPDATE account SET balance = balance + %s WHERE user_id = %s", (amount, session['user_id']))
        elif transaction_type == 'Withdraw':
            if balance >= amount:
                cursor.execute("UPDATE account SET balance = balance - %s WHERE user_id = %s", (amount, session['user_id']))
            else:
                flash('Insufficient balance!', 'danger')
        db.commit()
    cursor.execute("SELECT balance FROM account WHERE user_id = %s", (session['user_id'],))
    balance = cursor.fetchone()[0] if cursor.fetchone() else 0
    return render_template('transactions.html', balance=balance)

@app.route('/bills', methods=['GET', 'POST'])
def bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        due_date = request.form['due_date']
        amount = request.form['amount']
        cursor.execute("INSERT INTO bills (user_id, name, description, due_date, amount) VALUES (%s, %s, %s, %s, %s)", 
                       (session['user_id'], name, description, due_date, amount))
        db.commit()
    cursor.execute("SELECT * FROM bills WHERE user_id = %s", (session['user_id'],))
    bills = cursor.fetchall()
    return render_template('bills.html', bills=bills)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
'''