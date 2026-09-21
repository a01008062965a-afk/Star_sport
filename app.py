from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os, random, json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-star-sport-2026')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///starsport.db'
).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

VODAFONE_NUMBER = "01006654853"
NETWORK_NAME = "Star Sport Services"


# ============ الجداول ============
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    
card_number = db.Column(db.String(50), unique=True)phone = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100))
    expiry = db.Column(db.Date)
    package = db.Column(db.String(50), default='شهري')
    def to_dict(self):
        days = (self.expiry - datetime.now().date()).days if self.expiry else 0
        return {'phone': self.phone, 'name': self.name,
                'expiry': self.expiry.strftime('%Y-%m-%d') if self.expiry else '-',
                'package': self.package, 'days_left': days,
                'status': 'active' if days > 0 else 'expired'}


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='viewer')


class RenewalRequest(db.Model):
    __tablename__ = 'renewal_requests'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    name = db.Column(db.String(100))
    months = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    handled_by = db.Column(db.String(50))
    def to_dict(self):
        return {'id': self.id, 'phone': self.phone, 'name': self.name,
                'months': self.months, 'status': self.status,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
                'handled_by': self.handled_by}


class SupportMessage(db.Model):
    __tablename__ = 'support_messages'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    name = db.Column(db.String(100))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def to_dict(self):
        return {'id': self.id, 'phone': self.phone, 'name': self.name,
                'message': self.message, 'status': self.status,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''}


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    home = db.Column(db.String(100))
    away = db.Column(db.String(100))
    time = db.Column(db.String(20))
    channel = db.Column(db.String(100))
    league = db.Column(db.String(100))
    match_date = db.Column(db.Date, default=datetime.utcnow().date)
    def to_dict(self):
        return {'id': self.id, 'home': self.home, 'away': self.away,
                'time': self.time, 'channel': self.channel, 'league': self.league,
                'date': self.match_date.strftime('%Y-%m-%d') if self.match_date else ''}


# ============ الصفحات ============
@app.route('/')
def home():
    return render_template('index.html', network=NETWORK_NAME)


@app.route('/renew')
def page_renew():
    return render_template('renew.html', network=NETWORK_NAME)


@app.route('/vodafone')
def page_vodafone():
    return render_template('vodafone.html', number=VODAFONE_NUMBER, network=NETWORK_NAME)


@app.route('/remaining')
def page_remaining():
    return render_template('remaining.html', network=NETWORK_NAME)


@app.route('/matches')
def page_matches():
    matches = Match.query.filter_by(match_date=datetime.now().date()).all()
    return render_template('matches.html', matches=[m.to_dict() for m in matches], network=NETWORK_NAME)


@app.route('/azkar')
def page_azkar():
    return render_template('azkar.html', network=NETWORK_NAME)


@app.route('/quran')
def page_quran():
    return render_template('quran.html', network=NETWORK_NAME)


@app.route('/prayer')
def page_prayer():
    return render_template('prayer.html', network=NETWORK_NAME)


@app.route('/support')
def page_support():
    return render_template('support.html', network=NETWORK_NAME)


# ============ APIs ============
@app.route('/api/check', methods=['POST'])
def api_check():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'ok': False, 'msg': 'الرقم ده مش مسجل'}), 404
    return jsonify({'ok': True, 'user': user.to_dict()})


@app.route('/api/renew', methods=['POST'])
def api_renew():
    data = request.get_json() or {}
    phone = data.get('phone')
    months = int(data.get('months', 1))
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'ok': False, 'msg': 'المشترك غير موجود'}), 404
    existing = RenewalRequest.query.filter_by(phone=phone, status='pending').first()
    if existing:
        return jsonify({'ok': False, 'msg': 'فيه طلب معلق بالفعل'}), 400
    db.session.add(RenewalRequest(phone=phone, name=user.name, months=months))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إرسال الطلب'})


@app.route('/api/support', methods=['POST'])
def api_support():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    name = data.get('name', '').strip()
    message = data.get('message', '').strip()
    if not phone or not message:
        return jsonify({'ok': False, 'msg': 'اكمل البيانات'}), 400
    db.session.add(SupportMessage(phone=phone, name=name, message=message))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إرسال رسالتك'})


@app.route('/api/azkar')
def api_azkar():
    return jsonify(AZKAR)


@app.route('/api/quran')
def api_quran():
    return jsonify(random.choice(QURAN_AYAT))


@app.route('/api/prayer')
def api_prayer():
    return jsonify(PRAYER_TIMES_ASYUT)


# ============ الأدمن ============
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        admin = Admin.query.filter_by(username=u).first()
        if admin and check_password_hash(admin.password_hash, p):
            session['admin_id'] = admin.id
            session['admin_name'] = admin.name
            session['admin_role'] = admin.role
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
    return render_template('admin.html', admin_name=session['admin_name'],
                           admin_role=session['admin_role'])


@app.route('/api/admin/requests')
def api_admin_requests():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    reqs = RenewalRequest.query.order_by(RenewalRequest.created_at.desc()).all()
    return jsonify([r.to_dict() for r in reqs])


@app.route('/api/admin/messages')
def api_admin_messages():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    msgs = SupportMessage.query.order_by(SupportMessage.created_at.desc()).all()
    return jsonify([m.to_dict() for m in msgs])


@app.route('/api/admin/matches')
def api_admin_matches():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    ms = Match.query.order_by(Match.match_date.desc()).all()
    return jsonify([m.to_dict() for m in ms])


@app.route('/api/admin/users')
def api_admin_users():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([u.to_dict() for u in User.query.all()])


@app.route('/api/admin/handle', methods=['POST'])
def api_admin_handle():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    if session.get('admin_role') != 'super_admin':
        return jsonify({'ok': False, 'msg': 'مش عندك صلاحية'}), 403
    data = request.get_json() or {}
    req = RenewalRequest.query.get(data.get('id'))
    if not req: return jsonify({'ok': False}), 404
    if data.get('action') == 'approve':
        user = User.query.filter_by(phone=req.phone).first()
        if user:
            base = user.expiry if user.expiry and user.expiry > datetime.now().date() else datetime.now().date()
            user.expiry = base + timedelta(days=30 * req.months)
        req.status = 'approved'
    else:
        req.status = 'rejected'
    req.handled_by = session['admin_name']
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/add_match', methods=['POST'])
def api_admin_add_match():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    db.session.add(Match(home=d.get('home'), away=d.get('away'),
                         time=d.get('time'), channel=d.get('channel'),
                         league=d.get('league')))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/del_match/<int:id>', methods=['DELETE'])
def api_admin_del_match(id):
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    m = Match.query.get(id)
    if m: db.session.delete(m); db.session.commit()
    return jsonify({'ok': True})


# ============ البيانات ============


# ============ أول تشغيل ============
@app.before_request
def init_data():
    if not getattr(app, '_initialized', False):
        db.create_all()
        if not Admin.query.first():
            db.session.add(Admin(username='admin',
                password_hash=generate_password_hash('Star@2026'),
                name='المدير العام', role='super_admin'))
            db.session.add(Admin(username='employee1',
                password_hash=generate_password_hash('Emp@2026'),
                name='الموظف', role='viewer'))
        if not User.query.first():
            today = datetime.now().date()
            db.session.add(User(phone='01006654853', name='مشترك تجريبي',
                                expiry=today + timedelta(days=30), package='شهري'))
            db.session.add(User(phone='01111111111', name='أحمد',
                                expiry=today + timedelta(days=5), package='شهري'))
        db.session.commit()
        app._initialized = True



PRAYER_TIMES_ASYUT = {"city": "أسيوط", "times": {"الفجر": "04:22", "الشروق": "05:48", "الظهر": "11:51", "العصر": "15:13", "المغرب": "17:54", "العشاء": "19:10"}}


# تحميل البيانات من ملفات JSON
import json as _json
def _load(fname, default):
    try:
        with open(fname, 'r', encoding='utf-8') as _f:
            return _json.load(_f)
    except:
        return default

AZKAR = _load('azkar.json', [])
QURAN_AYAT = _load('quran.json', [])
PRAYER_TIMES_ASYUT = _load('prayer.json', {"city":"أسيوط","country":"مصر","times":{}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
