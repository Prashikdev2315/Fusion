"""Fusion URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

import notifications.urls
import debug_toolbar
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from applications.globals.views import RateLimitedPasswordResetView
from applications.health_center.user_management_controllers import (
    createUserController,
    getUsersController,
)
from applications.health_center.appointment_controllers import (
    ambulanceRequestsController,
    bookAppointmentController,
    createVisitController,
    getAppointmentsController,
    getDoctorAvailabilityController,
    getStaffAppointmentsController,
    updateStaffAppointmentStatusController,
    updateAmbulanceRequestStatusController,
    getVisitHistoryController,
)
from applications.health_center.patient_feature_controllers import (
    applyReimbursementController,
    downloadMedicalRecordsController,
    getDoctorsController,
    getMedicalRecordsController,
    getReimbursementStatusController,
)
from applications.health_center.staff_controllers import (
    searchPatientController,
    getPatientHistoryController,
    getPatientPendingAppointmentsController,
    createEnhancedVisitController,
    getVisitDetailController,
    createDoctorController,
    toggleDoctorStatusController,
    updateDoctorScheduleController,
    markDoctorAttendanceController,
    manageInventoryController,
    createMedicineController,
    getInventoryController,
    getAvailableMedicinesController,
    useMedicinesFromPrescriptionController,
    getDoctorsListForStaffController,
    getLowStockAlertsController,
    acknowledgeLowStockAlertController,
    getPHCNotificationsController,
    triggerPHCNotificationController,
    getRequisitionsController,
    createRequisitionController,
    approveRequisitionController,
    fulfillRequisitionController,
    logAmbulanceController,
    createAmbulanceLogController,
    getAmbulanceLogsController,
    createAnnouncementController,
    getAnnouncementsController,
    getSystemReportController,
    updateAppointmentStatusController,
    processReimbursementController,
    getReimbursementClaimsController,
    getPendingReimbursementClaimsController,
    verifyClaimController,
    updateClaimStatusController,
    processPaymentController,
)


urlpatterns = [
    url(r'^', include('applications.globals.urls')),
    url(r'^feeds/', include('applications.feeds.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^academic-procedures/', include('applications.academic_procedures.urls')),
    url(r'^aims/', include('applications.academic_information.urls')),
    url(r'^notifications/', include('applications.notifications_extension.urls')),
    url(r'^estate/', include('applications.estate_module.urls')),
    url(r'^dep/', include('applications.department.urls')),
    url(r'^programme_curriculum/',include('applications.programme_curriculum.urls')),
    url(r'^iwdModuleV2/', include('applications.iwdModuleV2.urls')),
    url(r'^__debug__/', include(debug_toolbar.urls)),
    url(r'^research_procedures/', include('applications.research_procedures.urls')),
    url(r'^accounts/', include('allauth.urls')),


    url(r'^eis/', include('applications.eis.urls')),
    url(r'^mess/', include('applications.central_mess.urls')),
    url(r'^complaint/', include('applications.complaint_system.urls')),
    url(r'^healthcenter/', include('applications.health_center.urls')),
    url(r'^phc/users/create/?$', createUserController, name='phc_create_user'),
    url(r'^phc/users/?$', getUsersController, name='phc_get_users'),
    url(r'^phc/appointments/book/?$', bookAppointmentController, name='phc_book_appointment'),
    url(r'^phc/appointments/my/?$', getAppointmentsController, name='phc_get_my_appointments'),
    url(r'^phc/appointments/?$', getStaffAppointmentsController, name='phc_get_staff_appointments'),
    url(r'^phc/doctors/?$', getDoctorsController, name='phc_get_doctors'),
    url(r'^phc/doctors/availability/?$', getDoctorAvailabilityController, name='phc_get_doctor_availability'),
    url(r'^phc/medical-records/?$', getMedicalRecordsController, name='phc_get_medical_records'),
    url(r'^phc/medical-records/download/?$', downloadMedicalRecordsController, name='phc_download_medical_records'),
    url(r'^phc/reimbursement/apply/?$', applyReimbursementController, name='phc_apply_reimbursement'),
    url(r'^phc/reimbursement/status/?$', getReimbursementStatusController, name='phc_reimbursement_status'),
    url(r'^phc/visit/create/?$', createVisitController, name='phc_create_visit'),
    url(r'^phc/visits/my/?$', getVisitHistoryController, name='phc_get_visit_history'),
    # Compatibility aliases for existing PHC frontend calls.
    url(r'^phc/api/appointments/?$', getAppointmentsController, name='phc_api_get_my_appointments'),
    url(r'^phc/api/appointments/book/?$', bookAppointmentController, name='phc_api_book_appointment'),
    url(r'^phc/api/ambulance/?$', ambulanceRequestsController, name='phc_api_ambulance'),
    url(r'^phc/api/staff/ambulance/request/status/?$', updateAmbulanceRequestStatusController, name='phc_api_staff_ambulance_request_status'),
    url(r'^phc/api/availability/?$', getDoctorAvailabilityController, name='phc_api_get_doctor_availability'),
    url(r'^phc/api/visit/create/?$', createVisitController, name='phc_api_create_visit'),
    url(r'^phc/api/visits/my/?$', getVisitHistoryController, name='phc_api_get_visit_history'),
    url(r'^phc/api/staff/appointments/?$', getStaffAppointmentsController, name='phc_api_get_staff_appointments'),
    url(r'^phc/api/staff/appointments/status/?$', updateStaffAppointmentStatusController, name='phc_api_staff_update_appointment_status'),
    url(r'^phc/staff/appointments/status/?$', updateStaffAppointmentStatusController, name='phc_staff_update_appointment_status'),
    
    # PHC Staff (Compounder) endpoints
    # UC-06: Patient Records
    url(r'^phc/staff/patient/search/?$', searchPatientController, name='phc_staff_search_patient'),
    url(r'^phc/staff/patient/(?P<patient_id>\d+)/history/?$', getPatientHistoryController, name='phc_staff_get_patient_history'),
    url(r'^phc/staff/patient/(?P<patient_id>\d+)/appointments/pending/?$', getPatientPendingAppointmentsController, name='phc_staff_get_pending_appointments'),
    url(r'^phc/staff/visit/create/?$', createEnhancedVisitController, name='phc_staff_create_visit'),
    url(r'^phc/staff/visit/(?P<visit_id>\d+)/?$', getVisitDetailController, name='phc_staff_get_visit_detail'),
    
    # UC-07: Doctor Schedule
    url(r'^phc/staff/doctor/create/?$', createDoctorController, name='phc_staff_create_doctor'),
    url(r'^phc/staff/doctor/schedule/?$', updateDoctorScheduleController, name='phc_staff_update_schedule'),
    url(r'^phc/staff/doctor/(?P<doctor_id>\d+)/toggle-status/?$', toggleDoctorStatusController, name='phc_staff_toggle_doctor_status'),
    
    # UC-08: Doctor Attendance  
    url(r'^phc/staff/doctor/attendance/?$', markDoctorAttendanceController, name='phc_staff_mark_attendance'),
    
    # UC-09: Inventory Management
    url(r'^phc/staff/inventory/?$', getInventoryController, name='phc_staff_get_inventory'),
    url(r'^phc/staff/inventory/medicine/create/?$', createMedicineController, name='phc_staff_create_medicine'),
    url(r'^phc/staff/inventory/manage/?$', manageInventoryController, name='phc_staff_manage_inventory'),
    url(r'^phc/staff/inventory/low-stock-alerts/?$', getLowStockAlertsController, name='phc_staff_get_low_stock_alerts'),
    url(r'^phc/staff/inventory/low-stock-alerts/acknowledge/?$', acknowledgeLowStockAlertController, name='phc_staff_acknowledge_low_stock_alert'),
    
    # Medicines for Prescriptions
    url(r'^phc/staff/medicines/available/?$', getAvailableMedicinesController, name='phc_staff_get_available_medicines'),
    url(r'^phc/staff/medicines/use/?$', useMedicinesFromPrescriptionController, name='phc_staff_use_medicines'),
    
    # Doctor Management (Staff View)
    url(r'^phc/staff/doctors/?$', getDoctorsListForStaffController, name='phc_staff_get_doctors'),
    
    # UC-10/UC-14: Requisition
    url(r'^phc/staff/requisitions/?$', getRequisitionsController, name='phc_staff_get_requisitions'),
    url(r'^phc/staff/requisition/create/?$', createRequisitionController, name='phc_staff_create_requisition'),
    url(r'^phc/staff/requisition/approve/?$', approveRequisitionController, name='phc_staff_approve_requisition'),
    url(r'^phc/staff/requisition/fulfill/?$', fulfillRequisitionController, name='phc_staff_fulfill_requisition'),
    
    # UC-11: Ambulance Logging
    url(r'^phc/ambulance/logs/?$', getAmbulanceLogsController, name='phc_get_ambulance_logs'),
    url(r'^phc/ambulance/logs/create/?$', createAmbulanceLogController, name='phc_create_ambulance_log'),
    url(r'^phc/staff/ambulance/log/?$', logAmbulanceController, name='phc_staff_log_ambulance'),
    url(r'^phc/staff/ambulance/request/status/?$', updateAmbulanceRequestStatusController, name='phc_staff_ambulance_request_status'),
    
    # UC-12: Announcements
    url(r'^phc/staff/announcement/create/?$', createAnnouncementController, name='phc_staff_create_announcement'),
    url(r'^phc/staff/announcements/?$', getAnnouncementsController, name='phc_staff_get_announcements'),

    # UC-13: System Reports
    url(r'^phc/staff/reports/?$', getSystemReportController, name='phc_staff_reports'),

    # UC-17 / BR-11: Notifications (endpoint-level implementation)
    url(r'^phc/staff/notifications/?$', getPHCNotificationsController, name='phc_staff_get_notifications'),
    url(r'^phc/staff/notifications/trigger/?$', triggerPHCNotificationController, name='phc_staff_trigger_notification'),

    # Appointment status updates (staff)
    url(r'^phc/staff/appointments/update-status/?$', updateAppointmentStatusController, name='phc_staff_update_appointment_status_v2'),
    
    # UC-15: Reimbursement Processing
    url(r'^phc/staff/reimbursement/claims/?$', getReimbursementClaimsController, name='phc_staff_get_reimbursement_claims'),
    url(r'^phc/staff/reimbursement/process/?$', processReimbursementController, name='phc_staff_process_reimbursement'),
    url(r'^phc/reimbursement/verify/?$', verifyClaimController, name='phc_reimbursement_verify'),
    url(r'^phc/reimbursement/pending/?$', getPendingReimbursementClaimsController, name='phc_reimbursement_pending'),
    url(r'^phc/reimbursement/update-status/?$', updateClaimStatusController, name='phc_reimbursement_update_status'),
    url(r'^phc/reimbursement/process-payment/?$', processPaymentController, name='phc_reimbursement_process_payment'),
    
    url(r'^leave/', include('applications.leave.urls')),
    url(r'^placement/', include('applications.placement_cell.urls')),
    url(r'^filetracking/', include('applications.filetracking.urls')),
    url(r'^spacs/', include('applications.scholarships.urls')),
    url(r'^visitorhostel/', include('applications.visitor_hostel.urls')),
    url(r'^office/', include('applications.office_module.urls')),
    url(r'^finance/', include('applications.finance_accounts.urls')),
    url(r'^purchase-and-store/', include('applications.ps1.urls')),
    url(r'^gymkhana/', include('applications.gymkhana.urls')),
    url(r'^library/', include('applications.library.urls')),
    url(r'^establishment/', include('applications.establishment.urls')),
    url(r'^ocms/', include('applications.online_cms.urls')),
    url(r'^counselling/', include('applications.counselling_cell.urls')),
    url(r'^hostelmanagement/', include('applications.hostel_management.urls')),
    url(r'^income-expenditure/', include('applications.income_expenditure.urls')),
    url(r'^hr2/', include('applications.hr2.urls')),
    url(r'^recruitment/', include('applications.recruitment.urls')),
    url(r'^examination/', include('applications.examination.urls')),
    url(r'^otheracademic/', include('applications.otheracademic.urls')),

    path(
        'password-reset/',
        RateLimitedPasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
        ),
        name='reset_password',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
