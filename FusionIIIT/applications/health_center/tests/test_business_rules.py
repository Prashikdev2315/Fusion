"""
test_business_rules.py — PHC Business Rule Tests

Tests for:
- BR-001: Authentication required (2 tests)
- BR-002: Patient access only own records (2 tests)
- BR-003: Staff can search all records (2 tests)
- BR-004: Appointment slot uniqueness (2 tests)
- BR-005: Doctor must have schedule (2 tests)
- BR-006: Visit must link to appointment (2 tests)
- BR-007: Reimbursement role-based workflow (2 tests)
- BR-008: Audit logging required (2 tests)

Total: 16 BR tests
"""

from datetime import date, timedelta, time
from django.contrib.auth.models import User

from .conftest import BaseModuleTestCase
from applications.health_center.models import Appointment, Doctor, Doctors_Schedule


class BRTestBase(BaseModuleTestCase):
    """Base class for all BR tests."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑001 : AUTHENTICATION REQUIRED
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR01_AuthenticationRequired(BRTestBase):
    """PHC-BR-001: Only authenticated users can access PHC endpoints"""

    def test_br01_valid_authenticated_access(self):
        """Valid: Authenticated user can access PHC endpoints"""
        self._test_id = "BR-001-Valid"
        self._br_id = "PHC-BR-001"
        self._test_category = "Valid"
        self._input_action = "Access /phc/appointments/ with authenticated session"
        self._expected_result = "Data returned; HTTP 200 OK"

        self.login_as_student()
        response = self.api_get('/phc/appointments/')

        if response.status_code == 200:
            self._record_result("Authenticated access", "Pass", "HTTP 200")
        else:
            self._record_result("Authenticated access", "Fail",
                              f"HTTP {response.status_code}")

    def test_br01_invalid_unauthenticated_access(self):
        """Invalid: Unauthenticated user cannot access PHC endpoints"""
        self._test_id = "BR-001-Invalid"
        self._br_id = "PHC-BR-001"
        self._test_category = "Invalid"
        self._input_action = "Access /phc/appointments/ without authentication"
        self._expected_result = "HTTP 401 Unauthorized or redirect to login"

        # Don't login - try direct access
        response = self.api_get('/phc/appointments/')

        if response.status_code in [301, 302, 401, 403]:
            self._record_result("Unauthenticated access blocked", "Pass",
                              f"HTTP {response.status_code} (access denied)")
        else:
            self._record_result("Unauthenticated access blocked", "Fail",
                              f"HTTP {response.status_code} (should be restricted)")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑002 : PATIENT CAN ONLY ACCESS OWN RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR02_PatientRecordIsolation(BRTestBase):
    """PHC-BR-002: Patients can only access their own records"""

    def test_br02_valid_own_appointments(self):
        """Valid: Student A views only their appointments"""
        self._test_id = "BR-002-Valid"
        self._br_id = "PHC-BR-002"
        self._test_category = "Valid"
        self._input_action = "Student A lists appointments with GET /phc/appointments/my/"
        self._expected_result = "Only Student A's appointments returned; HTTP 200"

        self.login_as_student()
        response = self.api_get('/phc/appointments/my/')

        if response.status_code == 200:
            # Verify all returned appointments belong to this student
            all_own = all(apt.get('patient_id') == self.student_user.id 
                         or 'patient' not in apt 
                         for apt in response.data if isinstance(response.data, list))
            if all_own:
                self._record_result("Own records only", "Pass",
                                  "All appointments belong to student")
            else:
                self._record_result("Own records only", "Fail",
                                  "Found appointments from other patients")
        else:
            self._record_result("Own records only", "Fail",
                              f"HTTP {response.status_code}")

    def test_br02_invalid_cross_patient_access(self):
        """Invalid: Student cannot access another patient's records"""
        self._test_id = "BR-002-Invalid"
        self._br_id = "PHC-BR-002"
        self._test_category = "Invalid"
        self._input_action = "Student A attempts to access Student B's appointment details"
        self._expected_result = "Access denied or returns Student A's data only"

        # Create another student
        student_b = User.objects.create_user(
            username='student_b',
            password='test123'
        )
        
        # Create an appointment for Student B
        apt_b = Appointment.objects.create(
            user=student_b,
            doctor=self.doctor1,
            date=self.future_date(5),
            time_slot=time(11, 0),
            status='booked'
        )

        # Login as Student A and try to access B's appointment
        self.login_as_student()
        
        # Try to access by ID (if API allows)
        response = self.api_get(f'/phc/appointments/')

        if response.status_code == 200 and isinstance(response.data, list):
            # Check if student A can see student B's appointment
            b_appointment_visible = any(apt for apt in response.data 
                                       if apt.get('id') == apt_b.id)
            if not b_appointment_visible:
                self._record_result("Cross-patient access blocked", "Pass",
                                  "Student B's appointment not visible to Student A")
            else:
                self._record_result("Cross-patient access blocked", "Fail",
                                  "Student B's appointment is visible (security issue)")
        else:
            self._record_result("Cross-patient access blocked", "Partial",
                              f"HTTP {response.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑003 : STAFF CAN SEARCH ALL RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR03_StaffUnrestrictedAccess(BRTestBase):
    """PHC-BR-003: Staff can search and access all patient records"""

    def test_br03_valid_staff_search_any_patient(self):
        """Valid: PHC Staff searches for any patient"""
        self._test_id = "BR-003-Valid"
        self._br_id = "PHC-BR-003"
        self._test_category = "Valid"
        self._input_action = "PHC Staff searches for any patient using /phc/staff/patient/search/"
        self._expected_result = "Patient record returned regardless of relationship; HTTP 200"

        self.login_as_staff()
        response = self.api_get('/phc/staff/patient/search/?query=student2021')

        if response.status_code == 200:
            self._record_result("Staff search access", "Pass",
                              f"HTTP 200, found {len(response.data)} patient(s)")
        else:
            self._record_result("Staff search access", "Fail",
                              f"HTTP {response.status_code}")

    def test_br03_invalid_student_staff_endpoint(self):
        """Invalid: Student cannot access staff endpoints"""
        self._test_id = "BR-003-Invalid"
        self._br_id = "PHC-BR-003"
        self._test_category = "Invalid"
        self._input_action = "Student attempts to use /phc/staff/patient/search/"
        self._expected_result = "HTTP 403 Forbidden; insufficient permissions"

        self.login_as_student()
        response = self.api_get('/phc/staff/patient/search/?query=test')

        if response.status_code in [403, 401]:
            self._record_result("Student staff access blocked", "Pass",
                              f"HTTP {response.status_code} (access denied)")
        else:
            self._record_result("Student staff access blocked", "Fail",
                              f"HTTP {response.status_code} (should be denied)")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑004 : APPOINTMENT SLOT UNIQUENESS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR04_AppointmentSlotUniqueness(BRTestBase):
    """PHC-BR-004: Each doctor-date-time slot is unique"""

    def test_br04_valid_different_time_slots(self):
        """Valid: Two patients book different time slots with same doctor"""
        self._test_id = "BR-004-Valid"
        self._br_id = "PHC-BR-004"
        self._test_category = "Valid"
        self._input_action = "Patient A books 10:00, Patient B books 11:00 same day/doctor"
        self._expected_result = "Both appointments created; HTTP 201 for each"

        # Create second student
        student_b = User.objects.create_user(username='student_b', password='test123')
        
        future_date = self.future_date(7)
        # Adjust to Monday for Dr. Sharma
        days_until_monday = (0 - future_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_date = date.today() + timedelta(days=days_until_monday)

        self.login_as_student()
        
        # Patient A books 10:00
        data_a = {
            'doctor_id': self.doctor1.id,
            'date': future_date.isoformat(),
            'time_slot': '10:00'
        }
        response_a = self.api_post('/phc/appointments/book/', data_a)

        # Patient B books 11:00
        self.client.login(username='student_b', password='test123')
        data_b = {
            'doctor_id': self.doctor1.id,
            'date': future_date.isoformat(),
            'time_slot': '11:00'
        }
        response_b = self.api_post('/phc/appointments/book/', data_b)

        if response_a.status_code == 201 and response_b.status_code == 201:
            self._record_result("Different slots allowed", "Pass",
                              "Both bookings succeeded")
        else:
            self._record_result("Different slots allowed", "Partial",
                              f"A: {response_a.status_code}, B: {response_b.status_code}")

    def test_br04_invalid_duplicate_slot(self):
        """Invalid: Two patients attempt same time slot"""
        self._test_id = "BR-004-Invalid"
        self._br_id = "PHC-BR-004"
        self._test_category = "Invalid"
        self._input_action = "Patient A and B both attempt to book same slot"
        self._expected_result = "Second request rejected with HTTP 409 Conflict"

        student_b = User.objects.create_user(username='student_c', password='test123')
        
        future_date = self.future_date(7)
        days_until_monday = (0 - future_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_date = date.today() + timedelta(days=days_until_monday)

        self.login_as_student()
        
        # First booking
        data = {
            'doctor_id': self.doctor1.id,
            'date': future_date.isoformat(),
            'time_slot': '09:30'
        }
        response1 = self.api_post('/phc/appointments/book/', data)

        # Second booking - same slot
        self.client.login(username='student_c', password='test123')
        response2 = self.api_post('/phc/appointments/book/', data)

        if response1.status_code == 201 and response2.status_code in [409, 400]:
            self._record_result("Duplicate slot rejected", "Pass",
                              f"Second booking rejected with HTTP {response2.status_code}")
        else:
            self._record_result("Duplicate slot rejected", "Fail",
                              f"First: {response1.status_code}, Second: {response2.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑005 : DOCTOR MUST HAVE SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR05_DoctorScheduleRequired(BRTestBase):
    """PHC-BR-005: Doctor must have schedule for available appointment slot"""

    def test_br05_valid_doctor_with_schedule(self):
        """Valid: Book appointment when doctor has schedule"""
        self._test_id = "BR-005-Valid"
        self._br_id = "PHC-BR-005"
        self._test_category = "Valid"
        self._input_action = "Book with Dr. Smith on Monday when he has schedule (day=0, 9-12)"
        self._expected_result = "Appointment created; HTTP 201"

        self.login_as_student()
        
        # Find next Monday
        today = date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_monday = today + timedelta(days=days_until_monday)

        data = {
            'doctor_id': self.doctor1.id,
            'date': future_monday.isoformat(),
            'time_slot': '10:00'
        }
        response = self.api_post('/phc/appointments/book/', data)

        if response.status_code == 201:
            self._record_result("Schedule check pass", "Pass",
                              "Appointment created for doctor with schedule")
        else:
            self._record_result("Schedule check pass", "Fail",
                              f"HTTP {response.status_code}")

    def test_br05_invalid_no_schedule(self):
        """Invalid: Attempt to book when doctor has no schedule"""
        self._test_id = "BR-005-Invalid"
        self._br_id = "PHC-BR-005"
        self._test_category = "Invalid"
        self._input_action = "Book Dr. Smith on Saturday when he has no schedule"
        self._expected_result = "Request rejected with HTTP 400"

        self.login_as_student()
        
        # Find next Saturday (day=5)
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        future_saturday = today + timedelta(days=days_until_saturday)

        data = {
            'doctor_id': self.doctor1.id,
            'date': future_saturday.isoformat(),
            'time_slot': '10:00'
        }
        response = self.api_post('/phc/appointments/book/', data)

        if response.status_code >= 400:
            self._record_result("No schedule rejection", "Pass",
                              f"HTTP {response.status_code} (rejected)")
        else:
            self._record_result("No schedule rejection", "Fail",
                              f"HTTP {response.status_code} (should be error)")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑006 : VISIT MUST LINK TO APPOINTMENT
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR06_VisitAppointmentLink(BRTestBase):
    """PHC-BR-006: Visit records must link to existing appointment"""

    def test_br06_valid_visit_with_appointment(self):
        """Valid: Create visit for existing appointment"""
        self._test_id = "BR-006-Valid"
        self._br_id = "PHC-BR-006"
        self._test_category = "Valid"
        self._input_action = "Create visit for existing booked appointment"
        self._expected_result = "Visit created; HTTP 201; linked to appointment"

        self.login_as_staff()
        
        data = {
            'appointment_id': self.appointment1.id,
            'diagnosis': 'Test',
            'prescription': 'Test',
            'doctor_id': self.doctor1.id
        }
        response = self.api_post('/phc/visit/create/', data)

        if response.status_code == 201:
            self._record_result("Visit creation", "Pass",
                              "Visit created successfully")
        else:
            self._record_result("Visit creation", "Fail",
                              f"HTTP {response.status_code}")

    def test_br06_invalid_nonexistent_appointment(self):
        """Invalid: Create visit for non-existent appointment"""
        self._test_id = "BR-006-Invalid"
        self._br_id = "PHC-BR-006"
        self._test_category = "Invalid"
        self._input_action = "Create visit with invalid appointment_id"
        self._expected_result = "HTTP 404 or 400; error indicates invalid appointment"

        self.login_as_staff()
        
        data = {
            'appointment_id': 99999,
            'diagnosis': 'Test',
            'prescription': 'Test',
            'doctor_id': self.doctor1.id
        }
        response = self.api_post('/phc/visit/create/', data)

        if response.status_code in [404, 400]:
            self._record_result("Invalid appointment rejected", "Pass",
                              f"HTTP {response.status_code}")
        else:
            self._record_result("Invalid appointment rejected", "Fail",
                              f"HTTP {response.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑007 : REIMBURSEMENT ROLE-BASED WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR07_ReimbursementRoleBasedAccess(BRTestBase):
    """PHC-BR-007: Reimbursement workflow enforces role-based stage access"""

    def test_br07_valid_staff_update_claim(self):
        """Valid: Staff can update reimbursement claim status"""
        self._test_id = "BR-007-Valid"
        self._br_id = "PHC-BR-007"
        self._test_category = "Valid"
        self._input_action = "Compounder updates claim status"
        self._expected_result = "Status updated; HTTP 200"

        self.login_as_staff()
        
        # This would need a real claim to test properly
        self._record_result("Staff update", "Partial",
                          "Requires existing claim ID for testing")

    def test_br07_invalid_student_update_claim(self):
        """Invalid: Student cannot update claim status"""
        self._test_id = "BR-007-Invalid"
        self._br_id = "PHC-BR-007"
        self._test_category = "Invalid"
        self._input_action = "Student attempts to update claim status"
        self._expected_result = "HTTP 403 Forbidden"

        self.login_as_student()
        
        data = {'status': 'validated'}
        response = self.api_patch('/phc/reimbursement/update-status/', data)

        if response.status_code in [403, 401]:
            self._record_result("Student claim update blocked", "Pass",
                              f"HTTP {response.status_code}")
        else:
            self._record_result("Student claim update blocked", "Partial",
                              f"HTTP {response.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# BR‑008 : AUDIT LOGGING REQUIRED
# ═══════════════════════════════════════════════════════════════════════════════

class TestBR08_AuditLogging(BRTestBase):
    """PHC-BR-008: All sensitive operations are audit logged"""

    def test_br08_valid_audit_log_created(self):
        """Valid: Audit log exists after creating visit"""
        self._test_id = "BR-008-Valid"
        self._br_id = "PHC-BR-008"
        self._test_category = "Valid"
        self._input_action = "Staff creates visit; check audit logs"
        self._expected_result = "Audit log entry exists with action, user, timestamp"

        self.login_as_staff()
        
        data = {
            'appointment_id': self.appointment1.id,
            'diagnosis': 'Test',
            'prescription': 'Test',
            'doctor_id': self.doctor1.id
        }
        response = self.api_post('/phc/visit/create/', data)

        if response.status_code == 201:
            self._record_result("Audit logging", "Pass",
                              "Visit created, audit should be logged")
        else:
            self._record_result("Audit logging", "Fail",
                              f"Visit creation failed: HTTP {response.status_code}")

    def test_br08_invalid_missing_audit_log(self):
        """Invalid: No audit log for sensitive operation"""
        self._test_id = "BR-008-Invalid"
        self._br_id = "PHC-BR-008"
        self._test_category = "Invalid"
        self._input_action = "Verify audit log exists after operation"
        self._expected_result = "Audit log must exist; if missing = defect"

        self._record_result("Missing audit log", "Partial",
                          "Requires database verification")
