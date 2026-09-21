from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os, json, urllib.request, urllib.parse, random

app = Flask(__name__)
app.secret_key = "starsport-2026-secret"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///starsport.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
VODAFONE = "01006654853"
WHATSAPP_NUMBER = "201003658928"
NETWORK = "Star Sport Services"


def load_json(fname, default):
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default


def send_whatsapp(msg):
    try:
        api_key = "YOUR_CALLMEBOT_KEY"
        if api_key == "YOUR_CALLMEBOT_KEY":
            return
        text = urllib.parse.quote(msg)
        url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_NUMBER}&text={text}&apikey={api_key}"
        urllib.request.urlopen(url, timeout=5)
    except Exception as e:
        print("WA error:", e)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    card_number = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    expiry = db.Column(db.Date)
    package = db.Column(db.String(50), default='شهري')

    def to_dict(self):
        days = (self.expiry - datetime.now().date()).days if self.expiry else 0
        return {
            'phone': self.phone, 'card_number': self.card_number,
            'name': self.name,
            'expiry': self.expiry.strftime('%Y-%m-%d') if self.expiry else '-',
            'package': self.package, 'days_left': days,
            'status': 'active' if days > 0 else 'expired'
        }


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='viewer')


class RenewalRequest(db.Model):
    __tablename__ = 'renewal_requests'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    card_number = db.Column(db.String(100))
    name = db.Column(db.String(100))
    months = db.Column(db.Integer)
    from_phone = db.Column(db.String(20))
    screenshot = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    handled_by = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id, 'phone': self.phone, 'card_number': self.card_number,
            'name': self.name, 'months': self.months, 'from_phone': self.from_phone,
            'screenshot': self.screenshot, 'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'handled_by': self.handled_by
        }


class SupportMessage(db.Model):
    __tablename__ = 'support_messages'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    name = db.Column(db.String(100))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'phone': self.phone, 'name': self.name,
            'message': self.message, 'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''
        }


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    home = db.Column(db.String(100))
    away = db.Column(db.String(100))
    time = db.Column(db.String(20))
    channel = db.Column(db.String(100))
    league = db.Column(db.String(100))
    match_date = db.Column(db.Date)

    def to_dict(self):
        return {
            'id': self.id, 'home': self.home, 'away': self.away,
            'time': self.time, 'channel': self.channel, 'league': self.league,
            'date': self.match_date.strftime('%Y-%m-%d') if self.match_date else ''
        }


# ============ صفحات العميل ============
@app.route('/')
def home():
    return render_template('index.html', network=NETWORK)


@app.route('/renew')
def page_renew():
    return render_template('renew.html', network=NETWORK)


@app.route('/vodafone')
def page_vodafone():
    return render_template('vodafone.html', number=VODAFONE, network=NETWORK)


@app.route('/remaining')
def page_remaining():
    return render_template('remaining.html', network=NETWORK)


@app.route('/matches')
def page_matches():
    ms = Match.query.filter_by(match_date=datetime.now().date()).all()
    return render_template('matches.html', matches=[m.to_dict() for m in ms], network=NETWORK)


@app.route('/azkar')
def page_azkar():
    return render_template('azkar.html', network=NETWORK)


@app.route('/quran')
def page_quran():
    return render_template('quran.html', network=NETWORK)


@app.route('/prayer')
def page_prayer():
    return render_template('prayer.html', network=NETWORK)


@app.route('/support')
def page_support():
    return render_template('support.html', network=NETWORK)


# ============ APIs ============
@app.route('/api/check-card', methods=['POST'])
def api_check_card():
    d = request.get_json() or {}
    card = d.get('card_number', '').strip()
    u = User.query.filter_by(card_number=card).first()
    if not u:
        return jsonify({'ok': True, 'user': {'phone':'','card_number':card,'name':'','expiry':'-','days_left':0,'status':'new'}})
    return jsonify({'ok': True, 'user': u.to_dict()})


@app.route('/api/renew', methods=['POST'])
def api_renew():
    card = request.form.get('card_number', '').strip()
    months = int(request.form.get('months', 1))
    from_phone = request.form.get('from_phone', '').strip()

    if not card or not from_phone:
        return jsonify({'ok': False, 'msg': 'اكمل البيانات'}), 400

    # منع تكرار الطلب
    existing = RenewalRequest.query.filter_by(card_number=card, status='pending').first()
    if existing:
        return jsonify({'ok': False, 'msg': 'فيه طلب معلق بالفعل — استنى الموافقة'}), 400

    # نجيب الاسم من الداتابيز لو موجود
    u = User.query.filter_by(card_number=card).first()
    name = u.name if u else ''

    fn = None
    if 'screenshot' in request.files:
        f = request.files['screenshot']
        if f and f.filename:
            ext = f.filename.rsplit('.', 1)[-1].lower()
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                fn = secure_filename(card + "_" + str(int(datetime.now().timestamp())) + "." + ext)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))

    req = RenewalRequest(
        phone=u.phone if u else from_phone,
        card_number=card, name=name, months=months,
        from_phone=from_phone, screenshot=fn
    )
    db.session.add(req)
    db.session.commit()

    send_whatsapp(f"طلب تجديد جديد\nالرقم المشفر: {card}\nالمدة: {months} شهر\nالرقم اللي حوّل: {from_phone}")

    return jsonify({'ok': True, 'msg': 'تم إرسال الطلب'})


@app.route('/api/support', methods=['POST'])
def api_support():
    d = request.get_json() or {}
    p = d.get('phone', '').strip()
    m = d.get('message', '').strip()
    if not p or not m:
        return jsonify({'ok': False, 'msg': 'اكمل البيانات'}), 400
    db.session.add(SupportMessage(phone=p, name=d.get('name', ''), message=m))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم الإرسال'})


@app.route('/uploads/<filename>')
def uploaded(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/azkar')
def api_azkar():
    return jsonify(load_json('azkar.json', []))


@app.route('/api/quran')
def api_quran():
    q = load_json('quran.json', [])
    if not q:
        return jsonify({'surah': '-', 'ayah': '-', 'text': 'لا يوجد'})
    return jsonify(random.choice(q))


@app.route('/api/prayer')
def api_prayer():
    return jsonify(load_json('prayer.json', {"city": "أسيوط", "country": "مصر", "times": {}}))


# ============ الأدمن ============
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        a = Admin.query.filter_by(username=u).first()
        if a and check_password_hash(a.password_hash, p):
            session['admin_id'] = a.id
            session['admin_name'] = a.name
            session['admin_role'] = a.role
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='بيانات غلط')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_panel():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin.html', admin_name=session['admin_name'], admin_role=session['admin_role'])


@app.route('/api/admin/requests')
def api_admin_requests():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([r.to_dict() for r in RenewalRequest.query.order_by(RenewalRequest.created_at.desc()).all()])


@app.route('/api/admin/messages')
def api_admin_messages():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([m.to_dict() for m in SupportMessage.query.order_by(SupportMessage.created_at.desc()).all()])


@app.route('/api/admin/users')
def api_admin_users():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([u.to_dict() for u in User.query.all()])


@app.route('/api/admin/matches')
def api_admin_matches():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([m.to_dict() for m in Match.query.order_by(Match.match_date.desc()).all()])


@app.route('/api/admin/handle', methods=['POST'])
def api_admin_handle():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    if session.get('admin_role') != 'super_admin':
        return jsonify({'ok': False, 'msg': 'مش عندك صلاحية'}), 403
    d = request.get_json() or {}
    r = RenewalRequest.query.get(d.get('id'))
    if not r: return jsonify({'ok': False}), 404

    if d.get('action') == 'approve':
        u = User.query.filter_by(card_number=r.card_number).first()
        if u:
            base = u.expiry if u.expiry and u.expiry > datetime.now().date() else datetime.now().date()
            u.expiry = base + timedelta(days=30 * r.months)
            if r.from_phone:
                u.phone = r.from_phone
        else:
            # مشترك جديد — نسجله
            new_user = User(
                phone=r.from_phone or '',
                card_number=r.card_number,
                name=r.name or '',
                expiry=datetime.now().date() + timedelta(days=30 * r.months),
                package='شهري'
            )
            db.session.add(new_user)
        r.status = 'approved'
    else:
        r.status = 'rejected'
    r.handled_by = session['admin_name']
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/add_user', methods=['POST'])
def api_admin_add_user():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    if User.query.filter_by(card_number=d.get('card_number')).first():
        return jsonify({'ok': False, 'msg': 'موجود'}), 400
    try:
        exp = datetime.strptime(d.get('expiry', ''), '%Y-%m-%d').date()
    except:
        exp = datetime.now().date() + timedelta(days=30)
    db.session.add(User(
        phone=d.get('phone', ''), card_number=d.get('card_number'),
        name=d.get('name', ''), expiry=exp, package=d.get('package', 'شهري')
    ))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/del_user/<int:id>', methods=['DELETE'])
def api_admin_del_user(id):
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    u = User.query.get(id)
    if u: db.session.delete(u); db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/add_match', methods=['POST'])
def api_admin_add_match():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    try:
        md = datetime.strptime(d.get('date', ''), '%Y-%m-%d').date()
    except:
        md = datetime.now().date()
    db.session.add(Match(home=d.get('home'), away=d.get('away'), time=d.get('time'),
                         channel=d.get('channel'), league=d.get('league'), match_date=md))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/del_match/<int:id>', methods=['DELETE'])
def api_admin_del_match(id):
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    m = Match.query.get(id)
    if m: db.session.delete(m); db.session.commit()
    return jsonify({'ok': True})


@app.before_request
def init():
    if not getattr(app, '_init', False):
        db.create_all()
        if not Admin.query.first():
            db.session.add(Admin(username='admin', password_hash=generate_password_hash('Star@2026'), name='المدير', role='super_admin'))
            db.session.add(Admin(username='employee1', password_hash=generate_password_hash('Emp@2026'), name='الموظف', role='viewer'))
        if not User.query.first():
            t = datetime.now().date()
            db.session.add(User(phone='01006654853', card_number='1001', name='مشترك تجريبي', expiry=t + timedelta(days=30)))
            db.session.add(User(phone='01111111111', card_number='1002abc', name='أحمد', expiry=t + timedelta(days=5)))
        db.session.commit()
        app._init = True


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
