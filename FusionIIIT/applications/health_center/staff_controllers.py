"""
PHC Staff (Compounder) Controllers
Request/response handlers for staff endpoints
"""

import csv
import io
import traceback
from datetime import datetime

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from django.http import HttpResponse

from .staff_services import (
    searchPatientService,
    getPatientHistoryService,
    getPatientPendingAppointmentsService,
    enhanceVisitRecordService,
    getVisitDetailService,
    createDoctorService,
    toggleDoctorStatusService,
    updateDoctorScheduleService,
    markDoctorAttendanceService,
    manageInventoryService,
    createMedicineService,
    getInventoryService,
    getAvailableMedicinesService,
    useMedicinesFromPrescriptionService,
    getDoctorsListForStaffService,
    getLowStockAlertsService,
    acknowledgeLowStockAlertService,
    createRequisitionService,
    getRequisitionsForStaffService,
    approveRequisitionService,
    fulfillRequisitionService,
    logAmbulanceService,
    createAnnouncementService,
    getAnnouncementsService,
    getPHCNotificationsService,
    triggerPHCNotificationService,
    getSystemReportService,
    processReimbursementClaimService,
    getReimbursementClaimsForStaffService,
    getPendingReimbursementClaimsForAuditorService,
    approveProfessorReimbursementService,
    verifyClaimService,
    updateClaimStatusForAuditorService,
    processPaymentService,
    updateAppointmentStatusService,
    # UC-06: Manage Patient Records
    createVisitRecordService,
    addPrescriptionToVisitService,
    getPatientRecordsService,
    editVisitRecordService,
    # UC-11: Log Ambulance Usage
    createAmbulanceLogService,
    getAmbulanceLogsService,
    getAmbulanceLogDetailService,
    updateAmbulanceLogService,
    completeAmbulanceJourneyService,
    getAmbulanceStatsService,
    searchAmbulanceLogsService,
    # UC-13: Generate System Reports
    generateOperationalReportService,
    generateFinancialReportService,
    generateInventoryReportService,
    generatePatientCareReportService,
    generateAuditReportService,
    getAvailableReportsService,
    PHCStaffError,
    PHCStaffPermissionError,
)


# ===========================
# UC-06: PATIENT RECORDS
# ===========================

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def searchPatientController(request):
    """Search for patients by ID/name"""
    try:
        search_query = request.query_params.get('q', '')
        results = searchPatientService(search_query, request.user)
        return Response({
            'success': True,
            'data': results,
            'count': len(results),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error searching patients: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getPatientHistoryController(request, patient_id):
    """Get patient's complete medical history"""
    try:
        history = getPatientHistoryService(patient_id, request.user)
        return Response({
            'success': True,
            'data': history,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getPatientPendingAppointmentsController(request, patient_id):
    """Get ONLY pending/booked appointments for a patient (for visit record creation)"""
    try:
        appointments = getPatientPendingAppointmentsService(patient_id, request.user)
        return Response({
            'success': True,
            'data': appointments,
            'count': len(appointments),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createEnhancedVisitController(request):
    """Create detailed visit record for appointment or walk-in patient"""
    try:
        data = request.data
        visit = enhanceVisitRecordService(
            appointment_id=data.get('appointment_id'),
            diagnosis=data.get('diagnosis'),
            prescription=data.get('prescription'),
            patient_id=data.get('patient_id'),  # For walk-in visits
            doctor_id=data.get('doctor_id'),
            notes=data.get('notes'),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Visit record created successfully',
            'data': visit,
        }, status=status.HTTP_201_CREATED)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error creating visit: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getVisitDetailController(request, visit_id):
    """Get detailed visit record by visit ID"""
    try:
        visit = getVisitDetailService(visit_id=visit_id, request_user=request.user)
        return Response({
            'success': True,
            'data': visit,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error fetching visit: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================
# UC-07: DOCTOR SCHEDULE
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createDoctorController(request):
    """Create doctor record for staff management"""
    try:
        data = request.data
        doctor = createDoctorService(
            doctor_name=data.get('doctor_name'),
            doctor_phone=data.get('doctor_phone'),
            specialization=data.get('specialization'),
            request_user=request.user,
            active=data.get('active', True),
        )
        return Response({
            'success': True,
            'message': 'Doctor created successfully',
            'data': doctor,
        }, status=status.HTTP_201_CREATED)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def toggleDoctorStatusController(request, doctor_id):
    """Toggle doctor's active/inactive status"""
    try:
        doctor = toggleDoctorStatusService(
            doctor_id=doctor_id,
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': f"Doctor marked as {'ACTIVE' if doctor['active'] else 'INACTIVE'}",
            'data': doctor,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateDoctorScheduleController(request):
    """Update doctor's weekly schedule"""
    try:
        data = request.data
        schedule = updateDoctorScheduleService(
            doctor_id=data.get('doctor_id'),
            schedule_data=data.get('schedule', []),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Doctor schedule updated successfully',
            'data': schedule,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# UC-08: DOCTOR ATTENDANCE
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def markDoctorAttendanceController(request):
    """Mark doctor as available/departed"""
    try:
        data = request.data
        attendance = markDoctorAttendanceService(
            doctor_id=data.get('doctor_id'),
            status=data.get('status'),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': f'Doctor marked as {data.get("status")}',
            'data': attendance,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# UC-09: INVENTORY
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def manageInventoryController(request):
    """Add or deduct medicine stock"""
    try:
        data = request.data
        result = manageInventoryService(
            medicine_id=data.get('medicine_id'),
            quantity_change=data.get('quantity_change'),
            reason=data.get('reason', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Inventory updated successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createMedicineController(request):
    """Create medicine and initialize stock in inventory"""
    try:
        data = request.data
        medicine = createMedicineService(
            medicine_name=data.get('medicine_name'),
            brand_name=data.get('brand_name'),
            manufacturer_name=data.get('manufacturer_name'),
            constituents=data.get('constituents'),
            pack_size_label=data.get('pack_size_label'),
            initial_stock=data.get('initial_stock', 0),
            reorder_threshold=data.get('reorder_threshold', 10),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Medicine added successfully',
            'data': medicine,
        }, status=status.HTTP_201_CREATED)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getInventoryController(request):
    """Get current inventory overview"""
    try:
        low_stock_only = request.query_params.get('low_stock', 'false').lower() == 'true'
        inventory = getInventoryService(request.user, low_stock_only)
        return Response({
            'success': True,
            'data': inventory,
            'count': len(inventory),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAvailableMedicinesController(request):
    """Get medicines that are available in stock for prescription"""
    try:
        medicines = getAvailableMedicinesService(request.user)
        return Response({
            'success': True,
            'data': medicines,
            'count': len(medicines),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def useMedicinesFromPrescriptionController(request):
    """Use/reduce medicines from inventory when prescription is written"""
    try:
        print('Incoming data:', request.data)
        visit_id = request.data.get('visit_id')
        medicines = request.data.get('medicines')
        if medicines is None:
            medicines = request.data.get('items', [])

        print(
            'Parsed medicines payload info:',
            {
                'visit_id': visit_id,
                'wrapper_key': 'medicines' if request.data.get('medicines') is not None else 'items',
                'medicines_type': type(medicines).__name__,
                'count': len(medicines) if isinstance(medicines, list) else 'n/a',
            }
        )
        
        result = useMedicinesFromPrescriptionService(visit_id, medicines, request.user)
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print('ERROR in useMedicinesFromPrescriptionController:', str(e))
        print(traceback.format_exc())
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================
# DOCTOR & INVENTORY MANAGEMENT (STAFF VIEWS)
# ===========================

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getDoctorsListForStaffController(request):
    """Get doctors list with schedule and attendance (staff view)"""
    try:
        include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
        doctors = getDoctorsListForStaffService(request.user, include_inactive=include_inactive)
        return Response({
            'success': True,
            'data': doctors,
            'count': len(doctors),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getLowStockAlertsController(request):
    """Get active low stock alerts"""
    try:
        alerts = getLowStockAlertsService(request.user)
        return Response({
            'success': True,
            'data': alerts,
            'count': len(alerts),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def acknowledgeLowStockAlertController(request):
    """Acknowledge a low stock alert"""
    try:
        data = request.data
        result = acknowledgeLowStockAlertService(
            alert_id=data.get('alert_id'),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Low stock alert acknowledged',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getPHCNotificationsController(request):
    """Get PHC notification events (UC-17)."""
    try:
        limit = request.query_params.get('limit', 50)
        data = getPHCNotificationsService(request.user, limit=limit)
        return Response({
            'success': True,
            'data': data,
            'count': len(data),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def triggerPHCNotificationController(request):
    """Trigger a PHC notification event (UC-17)."""
    try:
        result = triggerPHCNotificationService(request.data, request.user)
        return Response({
            'success': True,
            'message': 'Notification triggered',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getSystemReportController(request):
    """UC-13: Generate system reports (JSON/CSV)."""
    try:
        report_type = request.query_params.get('report_type')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        output_format = str(request.query_params.get('format', 'json')).strip().lower()

        report = getSystemReportService(
            request_user=request.user,
            report_type=report_type,
            from_date=from_date,
            to_date=to_date,
        )

        if output_format == 'csv':
            rows = report.get('rows', [])
            headers = list(rows[0].keys()) if rows else ['message']

            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=headers)
            writer.writeheader()

            if rows:
                for row in rows:
                    writer.writerow(row)
            else:
                writer.writerow({'message': 'No data available for selected filters'})

            response = HttpResponse(buffer.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = (
                f'attachment; filename="phc_{report.get("report_type")}_{report.get("from_date")}_{report.get("to_date")}.csv"'
            )
            return response

        return Response({
            'success': True,
            'data': report,
            'count': len(report.get('rows', [])),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# UC-10/UC-14: REQUISITION
# ===========================

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getRequisitionsController(request):
    """List requisitions for staff dashboard"""
    try:
        requisitions = getRequisitionsForStaffService(request.user)
        return Response({
            'success': True,
            'data': requisitions,
            'count': len(requisitions),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error fetching requisitions: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createRequisitionController(request):
    """Create medicine requisition"""
    try:
        data = request.data
        requisition = createRequisitionService(
            items_data=data.get('items', []),
            reason=data.get('reason', ''),
            requested_supplies=data.get('requested_supplies', []),
            notes=data.get('notes', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Requisition created successfully',
            'data': requisition,
        }, status=status.HTTP_201_CREATED)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def approveRequisitionController(request):
    """UC-16: Approve or reject requisition"""
    try:
        data = request.data
        result = approveRequisitionService(
            requisition_id=data.get('requisition_id'),
            action=data.get('action'),
            notes=data.get('notes', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': f"Requisition {result['status']} successfully",
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def fulfillRequisitionController(request):
    """Mark requisition as fulfilled"""
    try:
        data = request.data
        result = fulfillRequisitionService(
            requisition_id=data.get('requisition_id'),
            items_fulfillment=data.get('items', []),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Requisition fulfilled successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# UC-09: APPOINTMENT STATUS
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateAppointmentStatusController(request):
    """Update appointment status from staff appointments dashboard."""
    try:
        data = request.data
        result = updateAppointmentStatusService(
            appointment_id=data.get('appointment_id'),
            new_status=data.get('status'),
            notes=data.get('notes', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Appointment status updated successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# UC-11: AMBULANCE
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logAmbulanceController(request):
    """Log ambulance usage"""
    try:
        data = request.data
        ambulance_log = logAmbulanceService(
            patient_name=data.get('patient_name'),
            pickup_location=data.get('pickup_location'),
            destination=data.get('destination'),
            status=data.get('status', 'requested'),
            request_user=request.user,
            notes=data.get('notes', ''),
        )
        return Response({
            'success': True,
            'message': 'Ambulance logged successfully',
            'data': ambulance_log,
        }, status=status.HTTP_201_CREATED)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)


# ===========================
# UC-12: ANNOUNCEMENTS
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createAnnouncementController(request):
    """Create PHC announcement"""
    try:
        data = request.data
        announcement = createAnnouncementService(
            title=data.get('title'),
            content=data.get('content'),
            request_user=request.user,
            expires_at=data.get('expires_at'),
        )
        return Response({
            'success': True,
            'message': 'Announcement published successfully',
            'data': announcement,
        }, status=status.HTTP_201_CREATED)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAnnouncementsController(request):
    """Get active announcements"""
    try:
        announcements = getAnnouncementsService(request.user)
        return Response({
            'success': True,
            'data': announcements,
            'count': len(announcements),
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error fetching announcements: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================
# UC-15: REIMBURSEMENT
# ===========================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def processReimbursementController(request):
    """Process reimbursement claim (forward/reject/return)"""
    try:
        data = request.data
        result = processReimbursementClaimService(
            claim_id=data.get('claim_id'),
            action=data.get('action'),
            notes=data.get('notes', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': f'Claim {data.get("action")} successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getReimbursementClaimsController(request):
    """Get reimbursement claims for staff review"""
    try:
        status_filter = request.query_params.get('status')
        claims = getReimbursementClaimsForStaffService(request.user, status_filter)
        return Response({
            'success': True,
            'data': claims,
            'count': len(claims),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getPendingReimbursementClaimsController(request):
    """Auditor view for pending reimbursement work items."""
    try:
        status_filter = request.query_params.get('status')
        claims = getPendingReimbursementClaimsForAuditorService(request.user, status_filter, request=request)
        return Response({
            'success': True,
            'data': claims,
            'count': len(claims),
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def verifyClaimController(request):
    """Explicit auditor verification action for reimbursement claims."""
    try:
        data = request.data
        result = verifyClaimService(
            claim_id=data.get('claim_id'),
            notes=data.get('notes', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Claim verified successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateClaimStatusController(request):
    """Auditor workflow transition endpoint (verify/forward/reject)."""
    try:
        data = request.data
        result = updateClaimStatusForAuditorService(
            claim_id=data.get('claim_id'),
            action=data.get('action'),
            notes=data.get('notes', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': f'Claim {str(data.get("action") or "").strip().lower()} successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def processPaymentController(request):
    """Auditor final payment stage for approved claims."""
    try:
        data = request.data
        result = processPaymentService(
            claim_id=data.get('claim_id'),
            notes=data.get('notes', ''),
            payment_reference=data.get('payment_reference', ''),
            request_user=request.user,
        )
        return Response({
            'success': True,
            'message': 'Payment processed successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# UC-06: MANAGE PATIENT RECORDS - CONTROLLERS
# ============================================================================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createVisitRecordController(request):
    """UC-06-M2: Create new visit record for patient"""
    try:
        patient_id = request.data.get('patient_id')
        visit_date = request.data.get('visit_date')
        
        if not patient_id or not visit_date:
            return Response({
                'success': False,
                'message': 'Missing required fields: patient_id, visit_date'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = createVisitRecordService(patient_id, visit_date, request.user)
        
        return Response({
            'success': True,
            'message': 'Visit record created successfully',
            'data': result
        }, status=status.HTTP_201_CREATED)
        
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error creating visit record: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def addPrescriptionToVisitController(request):
    """UC-06-M3: Add prescription to visit record"""
    try:
        visit_id = request.data.get('visit_id')
        doctor_id = request.data.get('doctor_id')
        diagnosis = request.data.get('diagnosis')
        notes = request.data.get('notes', '')
        medicines = request.data.get('medicines', [])
        
        if not visit_id or not doctor_id or not diagnosis:
            return Response({
                'success': False,
                'message': 'Missing required fields: visit_id, doctor_id, diagnosis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = addPrescriptionToVisitService(
            visit_id, doctor_id, medicines, diagnosis, notes, request.user
        )
        
        return Response({
            'success': True,
            'message': 'Prescription added to visit successfully',
            'data': result
        }, status=status.HTTP_201_CREATED)
        
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error adding prescription: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getPatientRecordsController(request, patient_id):
    """UC-06-M1: Get complete patient medical records"""
    try:
        result = getPatientRecordsService(patient_id, request.user)
        
        return Response({
            'success': True,
            'data': result
        }, status=status.HTTP_200_OK)
        
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error fetching patient records: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def editVisitRecordController(request, visit_id):
    """Edit visit record (diagnosis and notes)"""
    try:
        diagnosis = request.data.get('diagnosis')
        notes = request.data.get('notes', '')
        
        if not diagnosis:
            return Response({
                'success': False,
                'message': 'Missing required field: diagnosis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = editVisitRecordService(visit_id, diagnosis, notes, request.user)
        
        return Response({
            'success': True,
            'message': 'Visit record updated successfully',
            'data': result
        }, status=status.HTTP_200_OK)
        
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error updating visit: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# UC-11: LOG AMBULANCE USAGE - CONTROLLERS
# ============================================================================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createAmbulanceLogController(request):
    """POST /phc/ambulance/logs/create/ - Create new ambulance log"""
    try:
        data = request.data
        
        start_time = None
        end_time = None
        if data.get('start_time'):
            try:
                start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            except:
                pass
        if data.get('end_time'):
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except:
                pass
        
        ambulance_log = createAmbulanceLogService(
            patient_name=data.get('patient_name'),
            pickup_location=data.get('pickup_location'),
            destination=data.get('destination'),
            status=data.get('status', 'requested'),
            request_user=request.user,
            start_time=start_time,
            end_time=end_time,
            start_odometer=data.get('start_odometer'),
            end_odometer=data.get('end_odometer'),
            notes=data.get('notes', ''),
        )
        
        return Response({
            'success': True,
            'message': 'Ambulance log created successfully',
            'data': ambulance_log,
        }, status=status.HTTP_201_CREATED)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAmbulanceLogsController(request):
    """GET /phc/ambulance/logs/ - Retrieve ambulance logs"""
    try:
        filters = {
            'status': request.query_params.get('status'),
            'patient_name': request.query_params.get('patient_name'),
            'date_from': request.query_params.get('date_from'),
            'date_to': request.query_params.get('date_to'),
            'limit': request.query_params.get('limit', 50),
        }
        
        result = getAmbulanceLogsService(request.user, filters=filters)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAmbulanceLogDetailController(request, log_id):
    """GET /phc/ambulance/logs/{log_id}/ - Get log details"""
    try:
        result = getAmbulanceLogDetailService(log_id, request.user)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateAmbulanceLogController(request, log_id):
    """PUT /phc/ambulance/logs/{log_id}/update/ - Update log"""
    try:
        data = request.data
        
        end_time = None
        if data.get('end_time'):
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except:
                pass
        
        result = updateAmbulanceLogService(
            ambulance_log_id=log_id,
            request_user=request.user,
            status=data.get('status'),
            notes=data.get('notes'),
            end_time=end_time,
            end_odometer=data.get('end_odometer'),
        )
        
        return Response({
            'success': True,
            'message': 'Ambulance log updated successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def completeAmbulanceJourneyController(request, log_id):
    """PUT /phc/ambulance/logs/{log_id}/complete/ - Complete journey"""
    try:
        data = request.data
        
        end_time = None
        if data.get('end_time'):
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except:
                pass
        
        result = completeAmbulanceJourneyService(
            ambulance_log_id=log_id,
            request_user=request.user,
            end_time=end_time,
            end_odometer=data.get('end_odometer'),
            notes=data.get('notes', ''),
        )
        
        return Response({
            'success': True,
            'message': 'Ambulance journey completed',
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAmbulanceStatsController(request):
    """GET /phc/ambulance/logs/stats/ - Get statistics"""
    try:
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            except:
                date_from = None
        
        if date_to:
            try:
                date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            except:
                date_to = None
        
        result = getAmbulanceStatsService(request.user, date_from=date_from, date_to=date_to)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def searchAmbulanceLogsController(request):
    """GET /phc/ambulance/logs/search/ - Search logs"""
    try:
        search_query = request.query_params.get('q', '').strip()
        
        result = searchAmbulanceLogsService(request.user, search_query)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# UC-13: GENERATE SYSTEM REPORTS
# ============================================================================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generateOperationalReportController(request):
    """
    Generate operational statistics report
    POST /phc/reports/operational/
    """
    try:
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'success': False,
                'message': 'start_date and end_date are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report = generateOperationalReportService(start_date, end_date, request.user)
        
        return Response({
            'success': True,
            'message': 'Operational report generated successfully',
            'data': report,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'success': False,
            'message': f'Invalid date format: {str(e)}',
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generateFinancialReportController(request):
    """
    Generate financial/reimbursement report
    POST /phc/reports/financial/
    """
    try:
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'success': False,
                'message': 'start_date and end_date are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report = generateFinancialReportService(start_date, end_date, request.user)
        
        return Response({
            'success': True,
            'message': 'Financial report generated successfully',
            'data': report,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'success': False,
            'message': f'Invalid date format: {str(e)}',
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generateInventoryReportController(request):
    """
    Generate inventory status and utilization report
    POST /phc/reports/inventory/
    """
    try:
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'success': False,
                'message': 'start_date and end_date are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report = generateInventoryReportService(start_date, end_date, request.user)
        
        return Response({
            'success': True,
            'message': 'Inventory report generated successfully',
            'data': report,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'success': False,
            'message': f'Invalid date format: {str(e)}',
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generatePatientCareReportController(request):
    """
    Generate patient care statistics and trends report
    POST /phc/reports/patient-care/
    """
    try:
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'success': False,
                'message': 'start_date and end_date are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report = generatePatientCareReportService(start_date, end_date, request.user)
        
        return Response({
            'success': True,
            'message': 'Patient care report generated successfully',
            'data': report,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'success': False,
            'message': f'Invalid date format: {str(e)}',
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generateAuditReportController(request):
    """
    Generate system audit trail and compliance report
    POST /phc/reports/audit/
    """
    try:
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'success': False,
                'message': 'start_date and end_date are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report = generateAuditReportService(start_date, end_date, request.user)
        
        return Response({
            'success': True,
            'message': 'Audit report generated successfully',
            'data': report,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'success': False,
            'message': f'Invalid date format: {str(e)}',
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAvailableReportsController(request):
    """
    Get list of available report types
    GET /phc/reports/available/
    """
    try:
        reports = getAvailableReportsService(request.user)
        
        return Response({
            'success': True,
            'message': 'Available reports retrieved successfully',
            'data': reports,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def approveProfessorReimbursementController(request):
    """
    BR-08: Professor approves reimbursement claims pending professor approval
    POST /phc/reimbursement/professor-approval/
    """
    try:
        data = request.data
        claim_id = data.get('claim_id')
        action = data.get('action')  # 'approve' or 'reject'
        notes = data.get('notes', '')
        
        if not claim_id or not action:
            return Response({
                'success': False,
                'message': 'claim_id and action are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = approveProfessorReimbursementService(
            claim_id=claim_id,
            action=action,
            notes=notes,
            request_user=request.user,
        )
        
        return Response({
            'success': True,
            'data': result,
            'message': f'Claim {action}d by professor',
        }, status=status.HTTP_200_OK)
    
    except PHCStaffPermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
