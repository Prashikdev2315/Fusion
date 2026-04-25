from django import views
from django.conf.urls import url,include

from .views import *
from .user_management_controllers import createUserController, getUsersController
from .appointment_controllers import (
    bookAppointmentController,
    getAppointmentsController,
    getDoctorAvailabilityController,
    createVisitController,
    getVisitHistoryController,
    getStaffAppointmentsController,
    updateStaffAppointmentStatusController,
)
from .patient_feature_controllers import (
    getMedicalRecordsController,
    downloadMedicalRecordsController,
    applyReimbursementController,
    getReimbursementStatusController,
)
from .UC11_LOG_AMBULANCE_USAGE_CONTROLLERS import (
    ambulanceAvailabilityController,
    createAmbulanceLogController,
    getAmbulanceLogsController,
    getAmbulanceLogDetailController,
    updateAmbulanceLogController,
    completeAmbulanceJourneyController,
    getAmbulanceStatsController,
    searchAmbulanceLogsController,
)
from .UC11_STUDENT_AMBULANCE_CONTROLLER import (
    getStudentAmbulanceRequestsController,
)
from .staff_controllers import (
    searchPatientController,
    processReimbursementController,
    getReimbursementClaimsController,
    getPendingReimbursementClaimsController,
    approveProfessorReimbursementController,
    # Medicine Management
    getAvailableMedicinesController,
    useMedicinesFromPrescriptionController,
    # UC-06: Manage Patient Records
    createVisitRecordController,
    addPrescriptionToVisitController,
    getPatientRecordsController,
    editVisitRecordController,
    # UC-10/UC-14/UC-16: Requisition Management
    getRequisitionsController,
    createRequisitionController,
    approveRequisitionController,
    fulfillRequisitionController,
    # UC-13: Generate System Reports
    generateOperationalReportController,
    generateFinancialReportController,
    generateInventoryReportController,
    generatePatientCareReportController,
    generateAuditReportController,
    getAvailableReportsController,
)

from .auditor_controllers import (
    getAuditorActionHistoryController,
)

app_name = 'healthcenter'

urlpatterns = [

    # PHC user management endpoints
    url(r'^phc/users/create/?$', createUserController, name='phc_create_user'),
    url(r'^phc/users/?$', getUsersController, name='phc_get_users'),

    # PHC Appointment API endpoints
    url(r'^phc/appointments/book/?$', bookAppointmentController, name='phc_book_appointment'),
    url(r'^phc/appointments/my/?$', getAppointmentsController, name='phc_get_my_appointments'),
    url(r'^phc/appointments/staff/?$', getStaffAppointmentsController, name='phc_get_staff_appointments'),
    url(r'^phc/appointments/status/?$', updateStaffAppointmentStatusController, name='phc_update_appointment_status'),
    url(r'^phc/doctors/availability/?$', getDoctorAvailabilityController, name='phc_get_doctor_availability'),

    # PHC Visit API endpoints
    url(r'^phc/visits/create/?$', createVisitController, name='phc_create_visit'),
    url(r'^phc/visits/history/?$', getVisitHistoryController, name='phc_get_visit_history'),

    # PHC Medical Records API endpoints
    url(r'^phc/medical-records/?$', getMedicalRecordsController, name='phc_get_medical_records'),
    url(r'^phc/medical-records/download/?$', downloadMedicalRecordsController, name='phc_download_medical_records'),

    # PHC Patient Search API endpoints
    url(r'^phc/patients/search/?$', searchPatientController, name='phc_search_patients'),

    # PHC Reimbursement API endpoints
    url(r'^phc/reimbursement/apply/?$', applyReimbursementController, name='phc_apply_reimbursement'),
    url(r'^phc/reimbursement/status/?$', getReimbursementStatusController, name='phc_get_reimbursement_status'),
    url(r'^phc/reimbursement/pending/?$', getPendingReimbursementClaimsController, name='phc_get_pending_reimbursement_claims'),
    url(r'^phc/reimbursement/professor-approval/?$', approveProfessorReimbursementController, name='phc_professor_approve_reimbursement'),
    url(r'^phc/reimbursement/process/?$', processReimbursementController, name='phc_process_reimbursement'),
    url(r'^phc/reimbursement/claims/?$', getReimbursementClaimsController, name='phc_get_reimbursement_claims'),

    # Medicine Management Endpoints
    url(r'^phc/staff/medicines/available/?$', getAvailableMedicinesController, name='phc_get_available_medicines'),
    url(r'^phc/staff/medicines/use/?$', useMedicinesFromPrescriptionController, name='phc_use_medicines_from_prescription'),

    # UC-10/UC-14/UC-16: Requisition Management Endpoints
    url(r'^phc/staff/requisitions/?$', getRequisitionsController, name='phc_get_requisitions'),
    url(r'^phc/staff/requisition/create/?$', createRequisitionController, name='phc_create_requisition'),
    url(r'^phc/staff/requisition/approve/?$', approveRequisitionController, name='phc_approve_requisition'),
    url(r'^phc/staff/requisition/fulfill/?$', fulfillRequisitionController, name='phc_fulfill_requisition'),

    # UC-06: Manage Patient Records Endpoints
    url(r'^phc/visits/create/?$', createVisitRecordController, name='phc_create_visit_record'),
    url(r'^phc/visits/(?P<visit_id>[0-9]+)/add-prescription/?$', addPrescriptionToVisitController, name='phc_add_prescription'),
    url(r'^phc/patients/(?P<patient_id>[0-9]+)/records/?$', getPatientRecordsController, name='phc_get_patient_records'),
    url(r'^phc/visits/(?P<visit_id>[0-9]+)/edit/?$', editVisitRecordController, name='phc_edit_visit_record'),

    # UC-11: Log Ambulance Usage Endpoints
    url(r'^phc/ambulance/logs/create/?$', createAmbulanceLogController, name='phc_create_ambulance_log'),
    url(r'^phc/ambulance/logs/?$', getAmbulanceLogsController, name='phc_get_ambulance_logs'),
    url(r'^phc/ambulance/logs/(?P<log_id>[0-9]+)/?$', getAmbulanceLogDetailController, name='phc_get_ambulance_log_detail'),
    url(r'^phc/ambulance/logs/(?P<log_id>[0-9]+)/update/?$', updateAmbulanceLogController, name='phc_update_ambulance_log'),
    url(r'^phc/ambulance/logs/(?P<log_id>[0-9]+)/complete/?$', completeAmbulanceJourneyController, name='phc_complete_ambulance_journey'),
    url(r'^phc/ambulance/logs/stats/?$', getAmbulanceStatsController, name='phc_get_ambulance_stats'),
    url(r'^phc/ambulance/logs/search/?$', searchAmbulanceLogsController, name='phc_search_ambulance_logs'),
    url(r'^phc/ambulance/availability/?$', ambulanceAvailabilityController, name='phc_ambulance_availability'),
    url(r'^phc/ambulance/my-requests/?$', getStudentAmbulanceRequestsController, name='phc_student_ambulance_requests'),

    # UC-13: Generate System Reports Endpoints
    url(r'^phc/reports/available/?$', getAvailableReportsController, name='phc_get_available_reports'),
    url(r'^phc/reports/operational/?$', generateOperationalReportController, name='phc_generate_operational_report'),
    url(r'^phc/reports/financial/?$', generateFinancialReportController, name='phc_generate_financial_report'),
    url(r'^phc/reports/inventory/?$', generateInventoryReportController, name='phc_generate_inventory_report'),
    url(r'^phc/reports/patient-care/?$', generatePatientCareReportController, name='phc_generate_patient_care_report'),
    url(r'^phc/reports/audit/?$', generateAuditReportController, name='phc_generate_audit_report'),

    # UC-17: Auditor Action History Endpoint
    url(r'^phc/auditor/action-history/?$', getAuditorActionHistoryController, name='phc_auditor_action_history'),

    # health_center home page
    url(r'^$', healthcenter, name='healthcenter'),

    #views
    url(r'^compounder/view_prescription/(?P<prescription_id>[0-9]+)/$',compounder_view_prescription,name='view_prescription'),
    url(r'^compounder/view_file/(?P<file_id>[\w-]+)/$',view_file, name='view_file'),
    url(r'^compounder/$', compounder_view, name='compounder_view'),
    url(r'^student/$', student_view, name='student_view'),
    url(r'announcement/', announcement, name='announcement'),
    url(r'medical_profile/', medical_profile, name='medical_profile'),
    
    #database entry
    url(r'^schedule_entry', schedule_entry, name='schedule_entry'),
    url(r'^doctor_entry', doctor_entry, name='doctor_entry'),
    url(r'^compounder_entry', compounder_entry, name='compounder_entry'), 
   
    # #api
    # url(r'^api/',include('applications.health_center.api.urls'))
]