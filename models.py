from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session
from sqlalchemy.sql import func

class RoutingSession(Session):
    def get_bind(self, mapper=None, clause=None):
        try:
            # If flushing (writing), use the default (primary) bind
            if self._flushing:
                return super().get_bind(mapper, clause)
            
            # If it's a SELECT statement (reading), try to use the replica
            if clause is not None and hasattr(clause, 'is_select') and clause.is_select:
                return self.db.engines['replica']
        except (KeyError, AttributeError):
            # Fallback to default (primary) if replica is not configured or other error
            pass
            
        return super().get_bind(mapper, clause)

db = SQLAlchemy(session_options={'class_': RoutingSession})

class KtpRecord(db.Model):
    __tablename__ = 'ktp_records'

    nik = db.Column(db.String(16), primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    birth_place = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10))
    blood_type = db.Column(db.String(5))
    address = db.Column(db.Text, nullable=False)
    rt_rw = db.Column(db.String(10))
    village_kelurahan = db.Column(db.String(100))
    district_kecamatan = db.Column(db.String(100))
    religion = db.Column(db.String(20))
    marital_status = db.Column(db.String(20))
    occupation = db.Column(db.String(100))
    citizenship = db.Column(db.String(5), default='WNI')
    expiry_date = db.Column(db.String(20), default='SEUMUR HIDUP')
    registration_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            'nik': self.nik,
            'full_name': self.full_name,
            'birth_place': self.birth_place,
            'birth_date': self.birth_date.isoformat() if self.birth_date else None,
            'gender': self.gender,
            'blood_type': self.blood_type,
            'address': self.address,
            'rt_rw': self.rt_rw,
            'village_kelurahan': self.village_kelurahan,
            'district_kecamatan': self.district_kecamatan,
            'religion': self.religion,
            'marital_status': self.marital_status,
            'occupation': self.occupation,
            'citizenship': self.citizenship,
            'expiry_date': self.expiry_date,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # Storing plain/hashed password
