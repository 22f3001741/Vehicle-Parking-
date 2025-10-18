from app import db, bcrypt
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Add any other user fields if needed, e.g., name, email
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)  # Changed to nullable=True
    reservations = db.relationship('Reservation', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False) # Price per unit time
    address = db.Column(db.String(200), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    maximum_number_of_spots = db.Column(db.Integer, nullable=False)
    # Relationship to ParkingSpot
    spots = db.relationship('ParkingSpot', backref='parking_lot', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ParkingLot {self.prime_location_name}>'

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Unique identifier within the lot, e.g., "A1", "B5"
    spot_identifier = db.Column(db.String(20), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    # 'A' for Available, 'O' for Occupied
    status = db.Column(db.String(1), default='A', nullable=False)
    # Relationship to Reservation (one spot can have many reservations over time)
    # Use uselist=False for one-to-one if a spot can only have one *active* reservation
    reservation = db.relationship('Reservation', backref='parking_spot', uselist=False, lazy=True, primaryjoin="and_(ParkingSpot.id==Reservation.spot_id, Reservation.leaving_timestamp==None)") # Only link active reservation


    def __repr__(self):
        return f'<ParkingSpot {self.spot_identifier} in Lot {self.lot_id}>'

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Nullable initially, set when user releases spot
    leaving_timestamp = db.Column(db.DateTime, nullable=True)
    # Calculated when leaving, could be stored or calculated on demand
    parking_cost = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<Reservation Spot {self.spot_id} by User {self.user_id}>'