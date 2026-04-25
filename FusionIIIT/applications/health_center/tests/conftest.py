"""
conftest.py — PHC Module Test Setup & Shared Fixtures

Sets up test users (student, staff), test data (doctors, schedules, appointments),
and provides helper methods for API testing.
"""

import os
import json
import yaml
from pathlib import Path
from datetime import date, timedelta, datetime, time

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from applications.health_center.models import (
    Doctor, Doctors_Schedule, Appointment, Visit, All_Medicine, 
    Stock_entry, Present_Stock, MedicalProfile, PHCUserRoleProfile
)
from applications.globals.models import ExtraInfo


# ============================================================
# CONFIGURATION
# ============================================================

MODULE_NAME = "PHC"
TESTS_DIR = Path(__file__).parent
SPECS_DIR = TESTS_DIR / "specs"
REPORTS_DIR = TESTS_DIR / "reports"


def load_spec(filename):
    """Load a YAML spec file from specs/ directory."""
    filepath = SPECS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Spec file not found: {filepath}")
    with open(filepath, "r") as f:
        return yaml.safe_load(f)


def ensure_reports_dir():
    """Create reports/ directory if it doesn't exist."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# BASE TEST CASE
# ============================================================

class BaseModuleTestCase(TestCase):
    """Base test case for all PHC tests with shared setup and helper methods."""

    @classmethod
    def setUpTestData(cls):
        """Create test data: users, doctors, schedules, medicines."""
        
        # ── Create Student User ──
        cls.student_user = User.objects.create_user(
            username='student2021',
            password='test123',
            first_name='John',
            last_name='Student',
            email='student@test.com'
        )
        
        # Create ExtraInfo for student
        cls.student_extra = ExtraInfo.objects.create(
            user=cls.student_user,
            id_='student2021',
            user_type='student'
        )
        
        # Create Medical Profile for student
        cls.student_medical = MedicalProfile.objects.create(
            user_id=cls.student_extra,
            date_of_birth=date(2000, 1, 15),
            gender='M',
            blood_type='O+',
            height=5.9,
            weight=75
        )

        # ── Create Staff User ──
        cls.staff_user = User.objects.create_user(
            username='staff_phc',
            password='test123',
            first_name='Admin',
            last_name='Staff',
            email='staff@test.com'
        )
        
        # Create ExtraInfo for staff
        cls.staff_extra = ExtraInfo.objects.create(
            user=cls.staff_user,
            id_='staff001',
            user_type='staff'
        )
        
        # Create PHC Role Profile for staff
        cls.staff_role = PHCUserRoleProfile.objects.create(
            user=cls.staff_user,
            role='phc_staff'
        )

        # ── Create Doctors ──
        cls.doctor1 = Doctor.objects.create(
            doctor_name='Dr. Sharma',
            doctor_phone='9876543210',
            specialization='General Medicine',
            active=True
        )
        
        cls.doctor2 = Doctor.objects.create(
            doctor_name='Dr. Patel',
            doctor_phone='9876543211',
            specialization='Cardiology',
            active=True
        )

        # ── Create Doctor Schedules ──
        # Dr. Sharma: Monday-Friday, 9:00-12:00, Room 101
        for day in range(5):  # Monday=0 to Friday=4
            Doctors_Schedule.objects.create(
                doctor_id=cls.doctor1,
                day=str(day),
                from_time=time(9, 0),
                to_time=time(12, 0),
                room=101
            )
        
        # Dr. Patel: Tuesday-Thursday, 14:00-17:00, Room 102
        for day in [1, 2, 3]:  # Tuesday, Wednesday, Thursday
            Doctors_Schedule.objects.create(
                doctor_id=cls.doctor2,
                day=str(day),
                from_time=time(14, 0),
                to_time=time(17, 0),
                room=102
            )

        # ── Create Medicines ──
        cls.medicine1 = All_Medicine.objects.create(
            medicine_name='Aspirin',
            brand_name='Aspirin 500mg',
            constituents='Acetylsalicylic acid',
            manufacturer_name='PharmaCorp',
            threshold=10,
            pack_size_label='10 tablets'
        )
        
        cls.medicine2 = All_Medicine.objects.create(
            medicine_name='Paracetamol',
            brand_name='Crocin 500mg',
            constituents='Paracetamol',
            manufacturer_name='GlaxoSmithKline',
            threshold=20,
            pack_size_label='15 tablets'
        )

        # ── Create Stock Entries ──
        cls.stock1 = Stock_entry.objects.create(
            medicine_id=cls.medicine1,
            quantity=100,
            supplier='Medical Supplies Inc',
            Expiry_date=date(2027, 12, 31)
        )
        
        cls.stock2 = Stock_entry.objects.create(
            medicine_id=cls.medicine2,
            quantity=150,
            supplier='PharmaTrade Ltd',
            Expiry_date=date(2027, 6, 30)
        )

        # ── Create Present Stock ──
        cls.present_stock1 = Present_Stock.objects.create(
            quantity=100,
            stock_id=cls.stock1,
            medicine_id=cls.medicine1,
            Expiry_date=date(2027, 12, 31)
        )
        
        cls.present_stock2 = Present_Stock.objects.create(
            quantity=150,
            stock_id=cls.stock2,
            medicine_id=cls.medicine2,
            Expiry_date=date(2027, 6, 30)
        )

        # ── Create Future Appointments ──
        future_date = date.today() + timedelta(days=5)
        cls.appointment1 = Appointment.objects.create(
            user=cls.student_user,
            doctor=cls.doctor1,
            date=future_date,
            time_slot=time(10, 0),
            status='booked'
        )

    def setUp(self):
        """Reset client for each test."""
        self.client = APIClient()
        self.factory = RequestFactory()

    # ── Helper Methods ──
    
    def login_as_student(self):
        """Log in as student user."""
        self.client.login(username='student2021', password='test123')
        return self.student_user

    def login_as_staff(self):
        """Log in as PHC staff user."""
        self.client.login(username='staff_phc', password='test123')
        return self.staff_user

    def api_get(self, url):
        """Perform GET request."""
        return self.client.get(url)

    def api_post(self, url, data=None):
        """Perform POST request."""
        return self.client.post(url, data, format='json')

    def api_patch(self, url, data=None):
        """Perform PATCH request."""
        return self.client.patch(url, data, format='json')

    def future_date(self, days_from_now):
        """Get a future date."""
        return date.today() + timedelta(days=days_from_now)

    def _record_result(self, step, status, evidence):
        """Record test step result for reporting."""
        if not hasattr(self, '_results'):
            self._results = []
        self._results.append({
            'step': step,
            'status': status,
            'evidence': evidence
        })

    def _record_step(self, step_description):
        """Record test step."""
        if not hasattr(self, '_steps'):
            self._steps = []
        self._steps.append(step_description)


# ── Test Metadata Decorators ──

def test_metadata(**kwargs):
    """Decorator to attach metadata to test methods."""
    def decorator(func):
        for key, value in kwargs.items():
            setattr(func, f'_{key}', value)
        return func
    return decorator
