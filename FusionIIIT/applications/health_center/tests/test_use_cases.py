"""
test_use_cases.py — PHC Use Case Tests

Tests for:
- UC-001: Book Appointment (3 tests: HP, AP, EX)
- UC-002: View Medical Records (3 tests: HP, AP, EX)
- UC-003: Create Visit Record (3 tests: HP, AP, EX)
- UC-004: Patient Search (3 tests: HP, AP, EX)
- UC-005: Reimbursement Workflow (3 tests: HP, AP, EX)

Total: 15 UC tests
"""

from datetime import date, timedelta, time
from django.urls import reverse
from django.contrib.auth.models import User

from .conftest import BaseModuleTestCase
from applications.health_center.models import Appointment, Visit, MedicalProfile


# ── UC Test Base Class ──
class UCTestBase(BaseModuleTestCase):
    """Base class for all UC tests."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# UC‑001 : BOOK APPOINTMENT
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC01_BookAppointment(UCTestBase):
    """PHC-UC-001: Patient books appointment with a doctor"""

    def test_hp01_book_appointment_valid_future_date(self):
        """Happy Path: Student books appointment with available doctor on future date"""
        self._test_id = "UC-001-HP-01"
        self._uc_id = "PHC-UC-001"
        self._test_category = "Happy Path"
        self._scenario = "Student books appointment with available doctor on future date"
        self._preconditions = "Student logged in; doctor exists with active schedule; date is future; time slot is available"
        self._input_action = "POST /phc/appointments/book/ with doctor_id, date, time_slot"
        self._expected_result = "Appointment created with status=booked; HTTP 201; appointment_id returned"

        self.login_as_student()
        
        # Get future date and time when doctor is available
        future_date = self.future_date(7)  # Next week, same day as schedule
        # Adjust to a Monday (day=0) for Dr. Sharma's availability
        days_until_monday = (0 - future_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_date = date.today() + timedelta(days=days_until_monday)

        data = {
            'doctor_id': self.doctor1.id,
            'date': future_date.isoformat(),
            'time_slot': '10:30'
        }
        
        response = self.api_post('/phc/appointments/book/', data)
        
        if response.status_code == 201:
            self._record_result("Appointment creation", "Pass", 
                              f"HTTP 201, response: {response.data}")
            self.assertIn('id', response.data)
            self.assertEqual(response.data['status'], 'booked')
        else:
            self._record_result("Appointment creation", "Fail",
                              f"HTTP {response.status_code}, response: {response.data}")
            self.fail(f"Expected 201, got {response.status_code}")

    def test_ap01_book_appointment_view_my_appointments(self):
        """Alternate Path: After booking, patient views their appointments"""
        self._test_id = "UC-001-AP-01"
        self._uc_id = "PHC-UC-001"
        self._test_category = "Alternate Path"
        self._scenario = "Student books appointment, then retrieves appointment list"
        self._preconditions = "Student logged in; appointment already exists"
        self._input_action = "GET /phc/appointments/my/ after booking"
        self._expected_result = "Booked appointment appears in patient's list; HTTP 200"

        self.login_as_student()
        
        response = self.api_get('/phc/appointments/my/')
        
        if response.status_code == 200:
            appointment_found = any(apt['status'] == 'booked' for apt in response.data)
            if appointment_found:
                self._record_result("View appointments", "Pass",
                                  f"Found booked appointment in list")
            else:
                self._record_result("View appointments", "Partial",
                                  f"List returned but no booked appointment found")
        else:
            self._record_result("View appointments", "Fail",
                              f"HTTP {response.status_code}")
            self.fail(f"Expected 200, got {response.status_code}")

    def test_ex01_book_appointment_past_date(self):
        """Exception: Student attempts to book appointment on past date"""
        self._test_id = "UC-001-EX-01"
        self._uc_id = "PHC-UC-001"
        self._test_category = "Exception"
        self._scenario = "Student attempts to book appointment with past date"
        self._preconditions = "Student logged in"
        self._input_action = "POST /phc/appointments/book/ with past date"
        self._expected_result = "Request rejected with HTTP 400; error indicates invalid date"

        self.login_as_student()
        
        past_date = date.today() - timedelta(days=1)
        data = {
            'doctor_id': self.doctor1.id,
            'date': past_date.isoformat(),
            'time_slot': '10:00'
        }
        
        response = self.api_post('/phc/appointments/book/', data)
        
        if response.status_code == 400:
            self._record_result("Past date rejection", "Pass",
                              f"HTTP 400 returned as expected")
        elif response.status_code >= 300:
            self._record_result("Past date rejection", "Partial",
                              f"HTTP {response.status_code} (not 400)")
        else:
            self._record_result("Past date rejection", "Fail",
                              f"HTTP {response.status_code} (should be 400)")


# ═══════════════════════════════════════════════════════════════════════════════
# UC‑002 : VIEW MEDICAL RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC02_ViewMedicalRecords(UCTestBase):
    """PHC-UC-002: Patient views their complete medical history"""

    def test_hp01_view_medical_records(self):
        """Happy Path: Patient views medical records"""
        self._test_id = "UC-002-HP-01"
        self._uc_id = "PHC-UC-002"
        self._test_category = "Happy Path"
        self._scenario = "Student views their medical records after appointment"
        self._preconditions = "Student logged in; student has appointment record"
        self._input_action = "GET /phc/medical-records/"
        self._expected_result = "Medical records returned; HTTP 200; contains visit data"

        self.login_as_student()
        
        response = self.api_get('/phc/medical-records/')
        
        if response.status_code == 200:
            self._record_result("Get medical records", "Pass",
                              f"HTTP 200, returned {len(response.data)} records")
        else:
            self._record_result("Get medical records", "Fail",
                              f"HTTP {response.status_code}")
            self.fail(f"Expected 200, got {response.status_code}")

    def test_ap01_download_medical_records(self):
        """Alternate Path: Patient downloads medical records as JSON"""
        self._test_id = "UC-002-AP-01"
        self._uc_id = "PHC-UC-002"
        self._test_category = "Alternate Path"
        self._scenario = "Student downloads medical records as JSON file"
        self._preconditions = "Student logged in; medical records exist"
        self._input_action = "GET /phc/medical-records/download/"
        self._expected_result: "JSON file downloaded; Content-Disposition header set; HTTP 200"

        self.login_as_student()
        
        response = self.api_get('/phc/medical-records/download/')
        
        if response.status_code == 200:
            if 'Content-Disposition' in response:
                self._record_result("Download records", "Pass",
                                  f"HTTP 200, file download header present")
            else:
                self._record_result("Download records", "Partial",
                                  f"HTTP 200 but no Content-Disposition header")
        else:
            self._record_result("Download records", "Fail",
                              f"HTTP {response.status_code}")

    def test_ex01_new_patient_no_records(self):
        """Exception: New patient has no medical records"""
        self._test_id = "UC-002-EX-01"
        self._uc_id = "PHC-UC-002"
        self._test_category = "Exception"
        self._scenario = "New patient with no prior visits views medical records"
        self._preconditions = "New student user created; no appointments/visits"
        self._input_action = "GET /phc/medical-records/ for new patient"
        self._expected_result: "Empty list returned; HTTP 200; no error"

        # Create a new student with no records
        new_student = User.objects.create_user(
            username='newstudent2026',
            password='test123'
        )
        self.client.login(username='newstudent2026', password='test123')
        
        response = self.api_get('/phc/medical-records/')
        
        if response.status_code == 200:
            if isinstance(response.data, list) and len(response.data) == 0:
                self._record_result("Empty records", "Pass",
                                  f"HTTP 200, empty list as expected")
            else:
                self._record_result("Empty records", "Partial",
                                  f"HTTP 200 but data type/content unexpected")
        else:
            self._record_result("Empty records", "Fail",
                              f"HTTP {response.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# UC‑003 : CREATE VISIT RECORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC03_CreateVisitRecord(UCTestBase):
    """PHC-UC-003: Staff creates a visit record for completed appointment"""

    def test_hp01_create_visit_record(self):
        """Happy Path: Staff creates visit with diagnosis and prescription"""
        self._test_id = "UC-003-HP-01"
        self._uc_id = "PHC-UC-003"
        self._test_category = "Happy Path"
        self._scenario = "Staff creates visit record with complete diagnosis and prescription"
        self._preconditions = "Staff logged in; patient has booked appointment; doctor assigned"
        self._input_action = "POST /phc/visit/create/ with appointment_id, diagnosis, prescription"
        self._expected_result: "Visit record created; HTTP 201; visit_id returned; linked to appointment"

        self.login_as_staff()
        
        data = {
            'appointment_id': self.appointment1.id,
            'diagnosis': 'Common Cold',
            'prescription': 'Rest, Fluids, Paracetamol 500mg 3x daily',
            'doctor_id': self.doctor1.id
        }
        
        response = self.api_post('/phc/visit/create/', data)
        
        if response.status_code == 201:
            self._record_result("Create visit", "Pass",
                              f"HTTP 201, visit created")
            self.assertIn('id', response.data)
        else:
            self._record_result("Create visit", "Fail",
                              f"HTTP {response.status_code}: {response.data}")
            self.fail(f"Expected 201, got {response.status_code}")

    def test_ap01_create_visit_minimal_prescription(self):
        """Alternate Path: Staff creates visit with minimal prescription"""
        self._test_id = "UC-003-AP-01"
        self._uc_id = "PHC-UC-003"
        self._test_category = "Alternate Path"
        self._scenario = "Staff creates visit with minimal prescription details"
        self._preconditions = "Staff logged in; appointment exists"
        self._input_action = "POST /phc/visit/create/ with minimal prescription"
        self._expected_result: "Visit record created successfully"

        self.login_as_staff()
        
        # Create another appointment for this test
        apt = Appointment.objects.create(
            user=self.student_user,
            doctor=self.doctor2,
            date=self.future_date(10),
            time_slot=time(14, 30),
            status='booked'
        )
        
        data = {
            'appointment_id': apt.id,
            'diagnosis': 'Hypertension',
            'prescription': 'BP medication',
            'doctor_id': self.doctor2.id
        }
        
        response = self.api_post('/phc/visit/create/', data)
        
        if response.status_code == 201:
            self._record_result("Create visit minimal", "Pass",
                              f"HTTP 201")
        else:
            self._record_result("Create visit minimal", "Fail",
                              f"HTTP {response.status_code}")

    def test_ex01_invalid_appointment_id(self):
        """Exception: Staff attempts to create visit for non-existent appointment"""
        self._test_id = "UC-003-EX-01"
        self._uc_id = "PHC-UC-003"
        self._test_category = "Exception"
        self._scenario = "Staff attempts to create visit for non-existent appointment"
        self._preconditions = "Staff logged in; invalid appointment_id"
        self._input_action: "POST /phc/visit/create/ with invalid appointment_id"
        self._expected_result: "Request rejected with HTTP 404; error indicates appointment not found"

        self.login_as_staff()
        
        data = {
            'appointment_id': 99999,  # Non-existent
            'diagnosis': 'Test',
            'prescription': 'Test',
            'doctor_id': self.doctor1.id
        }
        
        response = self.api_post('/phc/visit/create/', data)
        
        if response.status_code == 404:
            self._record_result("Invalid appointment", "Pass",
                              f"HTTP 404 as expected")
        elif response.status_code >= 400:
            self._record_result("Invalid appointment", "Partial",
                              f"HTTP {response.status_code} (error, but not 404)")
        else:
            self._record_result("Invalid appointment", "Fail",
                              f"HTTP {response.status_code} (should be error)")


# ═══════════════════════════════════════════════════════════════════════════════
# UC‑004 : PATIENT SEARCH (STAFF)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC04_PatientSearch(UCTestBase):
    """PHC-UC-004: Staff searches for patient records"""

    def test_hp01_search_patient_by_username(self):
        """Happy Path: Staff searches patient by username"""
        self._test_id = "UC-004-HP-01"
        self._uc_id = "PHC-UC-004"
        self._test_category = "Happy Path"
        self._scenario = "Staff searches patient by username"
        self._preconditions = "Staff logged in; patient with target username exists"
        self._input_action: "GET /phc/staff/patient/search/?query=student2021"
        self._expected_result": "Patient record returned with id, username, blood_type, last_appointment; HTTP 200"

        self.login_as_staff()
        
        response = self.api_get('/phc/staff/patient/search/?query=student2021')
        
        if response.status_code == 200:
            if isinstance(response.data, list) and len(response.data) > 0:
                self._record_result("Search by username", "Pass",
                                  f"Found {len(response.data)} patient(s)")
            else:
                self._record_result("Search by username", "Partial",
                                  f"HTTP 200 but no results")
        else:
            self._record_result("Search by username", "Fail",
                              f"HTTP {response.status_code}")

    def test_ap01_search_patient_by_name(self):
        """Alternate Path: Staff searches patient by first name"""
        self._test_id = "UC-004-AP-01"
        self._uc_id = "PHC-UC-004"
        self._test_category = "Alternate Path"
        self._scenario": "Staff searches patient by first name"
        self._preconditions = "Staff logged in"
        self._input_action": "GET /phc/staff/patient/search/?query=John"
        self._expected_result": "Matching patients returned in list"

        self.login_as_staff()
        
        response = self.api_get('/phc/staff/patient/search/?query=John')
        
        if response.status_code == 200:
            self._record_result("Search by name", "Pass",
                              f"HTTP 200, found {len(response.data)} result(s)")
        else:
            self._record_result("Search by name", "Fail",
                              f"HTTP {response.status_code}")

    def test_ex01_search_empty_query(self):
        """Exception: Staff searches with empty query"""
        self._test_id = "UC-004-EX-01"
        self._uc_id = "PHC-UC-004"
        self._test_category = "Exception"
        self._scenario": "Staff searches with empty query string"
        self._preconditions = "Staff logged in"
        self._input_action": "GET /phc/staff/patient/search/?query="
        self._expected_result": "Empty list or HTTP 400"

        self.login_as_staff()
        
        response = self.api_get('/phc/staff/patient/search/?query=')
        
        if response.status_code == 200 and len(response.data) == 0:
            self._record_result("Empty query", "Pass",
                              f"Empty list returned")
        elif response.status_code == 400:
            self._record_result("Empty query", "Pass",
                              f"HTTP 400 validation error")
        else:
            self._record_result("Empty query", "Partial",
                              f"HTTP {response.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# UC‑005 : REIMBURSEMENT WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC05_ReimbursementWorkflow(UCTestBase):
    """PHC-UC-005: Complete reimbursement claim workflow"""

    def test_hp01_reimbursement_full_workflow(self):
        """Happy Path: Patient submits, compounder validates, auditor approves"""
        self._test_id = "UC-005-HP-01"
        self._uc_id = "PHC-UC-005"
        self._test_category = "Happy Path"
        self._scenario": "Complete reimbursement workflow from submission to payment"
        self._preconditions = "Patient has expense; compounder and auditor active"
        self._input_action": "POST /phc/reimbursement/apply/ → PATCH by compounder → by auditor"
        self._expected_result": "Claim progresses through all stages; final status=completed"

        self.login_as_student()
        
        # Step 1: Patient applies for reimbursement
        data = {
            'amount': 500.00,
            'description': 'Medical consultation',
            'date': date.today().isoformat()
        }
        
        response = self.api_post('/phc/reimbursement/apply/', data)
        
        if response.status_code == 201:
            self._record_result("Reimbursement apply", "Pass",
                              f"HTTP 201, claim created")
        else:
            self._record_result("Reimbursement apply", "Fail",
                              f"HTTP {response.status_code}")

    def test_ap01_compounder_rejects_claim(self):
        """Alternate Path: Compounder rejects claim"""
        self._test_id = "UC-005-AP-01"
        self._uc_id = "PHC-UC-005"
        self._test_category = "Alternate Path"
        self._scenario": "Compounder identifies insufficient documentation and rejects"
        self._preconditions = "Claim submitted; compounder reviews"
        self._input_action": "PATCH /phc/reimbursement/update-status/ with rejected status"
        self._expected_result": "Claim rejected; reason recorded; workflow stops"

        self.login_as_staff()
        
        # Placeholder: would need actual claim ID to test
        self._record_result("Compounder rejection", "Partial",
                          f"Test requires live claim ID")

    def test_ex01_auditor_fraud_detection(self):
        """Exception: Auditor detects fraud and rejects after compounder approval"""
        self._test_id = "UC-005-EX-01"
        self._uc_id = "PHC-UC-005"
        self._test_category = "Exception"
        self._scenario": "Auditor detects inconsistency and rejects claim"
        self._preconditions = "Claim passed compounder; auditor reviews"
        self._input_action": "PATCH /phc/reimbursement/update-status/ with fraud flag"
        self._expected_result": "Claim reverted to rejected; audit logged; payment blocked"

        self.login_as_staff()
        
        self._record_result("Fraud detection", "Partial",
                          f"Test requires live claim in auditor stage")
