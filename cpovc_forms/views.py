from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import json
import random
import uuid
# from itertools import chain #
from datetime import datetime
from dateutil.relativedelta import relativedelta
from cpovc_forms.forms import (
    OVCSearchForm, ResidentialFollowupForm,
    ResidentialForm, OVC_FT3hForm, SearchForm, OVCCareSearchForm,
    OVC_CaseEventForm, DocumentsManager, OVCSchoolForm,
    OVCBursaryForm, BackgroundDetailsForm, OVC_FTFCForm,
    OVCCsiForm, OVCF1AForm, OVCHHVAForm, GOKBursaryForm,
    CaseInfoForm)
from cpovc_forms.models import (
    OVCEconomicStatus, OVCFamilyStatus, OVCReferral, OVCHobbies,
    OVCFriends, OVCDocuments, OVCMedical, OVCCaseRecord, OVCNeeds,
    OVCCaseCategory, OVCCaseSubCategory, FormsLog, OVCCaseEvents,
    OVCCaseEventServices, OVCCaseEventCourt, OVCPlacement,
    OVCPlacementFollowUp, OVCDischargeFollowUp, OVCEducationFollowUp,
    OVCEducationLevelFollowUp, OVCAdverseEventsFollowUp,
    OVCAdverseEventsOtherFollowUp, OVCCaseEventClosure,
    OVCCaseGeo, OVCMedicalSubconditions, OVCBursary, OVCFamilyCare,
    OVCCaseEventSummon, OVCCareEvents, OVCCarePriority,
    OVCCareServices, OVCCareEAV, OVCCareAssessment, OvcCasePersons,
    OVCCaseLocation)
from cpovc_ovc.models import OVCRegistration, OVCHouseHold
from cpovc_main.functions import (
    get_list_of_org_units, get_dict, get_vgeo_list, get_vorg_list,
    get_persons_list, get_list_of_persons, get_list, form_id_generator,
    case_event_id_generator, convert_date, new_guid_32,
    beneficiary_id_generator, translate_geo, translate,
    translate_case, translate_reverse, translate_reverse_org, translate_school)
from cpovc_forms.functions import (save_audit_trail)
from cpovc_main.country import (COUNTRIES)
from cpovc_registry.models import (
    RegOrgUnit, RegOrgUnitContact, RegOrgUnitGeography, RegPerson,
    RegPersonsOrgUnits, AppUser, RegPersonsSiblings,
    RegPersonsTypes, RegPersonsGuardians, RegPersonsGeo,
    RegPersonsExternalIds, RegOrgUnitsService)
from cpovc_main.models import (SetupList, SetupGeography, SchoolList)
from cpovc_auth.models import CPOVCUserRoleGeoOrg
from cpovc_auth.decorators import is_allowed_groups
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from cpovc_registry.functions import get_list_types, extract_post_params
from cpovc_ovc.functions import get_ovcdetails
from .functions import (
    create_fields, create_form_fields, save_form1b, get_case_geo,
    get_person_ids, get_exit, get_stay, save_bursary,
    get_placement, save_case_info, get_case_info,
    save_case_other_geos, handle_photo_upload, save_photo, get_photo)
from notifications.functions import send_notification
# For CTiP
from cpovc_ctip.settings import CATS
from cpovc_ctip.forms import CTIPForm
from cpovc_ctip.functions import handle_ctip, get_ctip


def validate_serialnumber(person_id, subcounty, serial_number):
    try:
        serial_number_exists = OVCCaseRecord.objects.filter(
            case_serial=serial_number, person_id=person_id)

        if serial_number_exists:
            return str(serial_number)
        else:
            # Get Year
            now = datetime.now()
            year = now.year

            # Get County
            countys = SetupGeography.objects.get(area_id=int(subcounty))
            county = countys.parent_area_id
            subcounty_code = countys.area_code

            # Get CaseRecordNumber(AuotIncremental)
            case_records = OVCCaseGeo.objects.filter(
                report_subcounty=subcounty).count()
            index = int(case_records) + 1

            serial_number = 'CCO/' + \
                str(county) + '/' + str(subcounty_code) + \
                '/5/29/' + str(index) + '/' + str(year)
    except Exception as e:
        raise e
    return str(serial_number)


def generate_serialnumber(request):
    try:
        if request.method == 'POST':
            serial_number = ''
            jsonCaseSerialNumber = []

            # Get Year
            now = datetime.now()
            year = now.year

            # Get SubCounty
            subcounty = request.POST.get('subcounty')

            # Get County
            countys = SetupGeography.objects.get(area_id=subcounty)
            county = countys.parent_area_id
            subcounty_code = countys.area_code

            # Get CaseRecordNumber(AuotIncremental)
            case_records = OVCCaseGeo.objects.filter(
                report_subcounty=subcounty).count()
            index = int(case_records) + 1

            serial_number = 'CCO/' + \
                str(county) + '/' + str(subcounty_code) + \
                '/5/29/' + str(index) + '/' + str(year)
            jsonCaseSerialNumber.append({'serial_number': serial_number})

            # print 'serial_number >> %s' % serial_number

    except Exception as e:
        raise e
    return JsonResponse(jsonCaseSerialNumber, content_type='application/json',
                        safe=False)


def userorgunits_lookup(request):
    # For JSON lookup stuff on Case Geo Locs pages

    try:
        if request.method == 'POST':
            jsonOrgUnitsResults = []
            org_unit_ids = ['TNSA', 'TNSI', 'TNCI', 'TNRH', 'TNRC', 'TNRR']
            # user_id = request.POST.get('user_id')
            types = int(request.POST.get('types'))

            # Get Logged User
            username = request.user.get_username()
            appuser = AppUser.objects.get(username=username)
            # user_id = appuser.id

            if types == 1:
                org_unit_ids = ['TNSA', 'TNSI', 'TNCI', 'TNRH', 'TNRC', 'TNRR']

                # Get RegPersonsGeo
                area_ids = []
                regpersonsgeo = RegPersonsGeo.objects.filter(
                    person=appuser.reg_person.id, is_void=False)
                if regpersonsgeo:
                    for regpersongeo in regpersonsgeo:
                        area_ids.append(regpersongeo.area_id)

                if area_ids:
                    # Get RegOrgUnitGeography
                    orgunits = []
                    regorgunitsgeography = RegOrgUnitGeography.objects.filter(
                        area_id__in=area_ids, is_void=False)
                    for regorgunitgeography in regorgunitsgeography:
                        if regorgunitgeography.org_unit_id not in orgunits:
                            orgunits.append(regorgunitgeography.org_unit_id)

                    # Get RegOrgUnit
                    # org_unit_ids = ['TNSA', 'TNSI', 'TNCI', 'TNRH', 'TNRC']
                    regorgunits = RegOrgUnit.objects.filter(
                        id__in=orgunits, is_void=False,
                        org_unit_type_id__in=org_unit_ids)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append(
                            {'id': regorgunit.id,
                             'org_unit_name': str(regorgunit.org_unit_name)})
                else:
                    # Get RegOrgUnit
                    # org_unit_ids = ['TNSA', 'TNSI', 'TNCI', 'TNRH', 'TNRC']
                    regorgunits = RegOrgUnit.objects.filter(
                        org_unit_type_id__in=org_unit_ids, is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append(
                            {'id': regorgunit.id,
                             'org_unit_name': str(regorgunit.org_unit_name)})
            if types == 2:
                orgunits = []

                # Get RegPersonsGeo
                area_ids = []
                regpersonsgeo = RegPersonsGeo.objects.filter(
                    person=appuser.reg_person.id, is_void=False)

                if regpersonsgeo:
                    for regpersongeo in regpersonsgeo:
                        area_ids.append(regpersongeo.area_id)

                if area_ids:
                    # print 'Non-national users ..'
                    # Get RegPersonsOrgUnits
                    regpersonorgunits = RegPersonsOrgUnits.objects.filter(
                        person=appuser.reg_person.id, is_void=False)
                    for regpersonorgunit in regpersonorgunits:
                        orgunits.append(regpersonorgunit.org_unit_id)

                    # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI', 'TNCI',
                    # 'TNRH', 'TNRC']
                    regorgunits = RegOrgUnit.objects.filter(
                        id__in=orgunits, is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append(
                            {'id': regorgunit.id,
                             'org_unit_name': str(regorgunit.org_unit_name)})
                else:
                    # print 'National users (DCS) ..'
                    # Get RegPersonsOrgUnits  - ALL
                    regpersonorgunits = RegPersonsOrgUnits.objects.filter(
                        is_void=False)

                    if regpersonorgunits:
                        for regpersonorgunit in regpersonorgunits:
                            orgunits.append(regpersonorgunit.org_unit_id)

                        # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI',
                        # 'TNCI', 'TNRH', 'TNRC']
                        regorgunits = RegOrgUnit.objects.filter(
                            id__in=orgunits, is_void=False)

                    else:
                        # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI',
                        # 'TNCI', 'TNRH', 'TNRC']
                        regorgunits = RegOrgUnit.objects.filter(is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append(
                            {'id': regorgunit.id,
                             'org_unit_name': str(regorgunit.org_unit_name)})
            if types == 3:
                # This will be used for Residential Placements
                ou_types = ['TNRH', 'TNRC', 'TNAP', 'TNRR', 'TNRB', 'TNRS']
                orgunits = []

                # Get RegPersonsGeo
                # RegPersonsOrgUnits
                area_ids = []
                regpersonsgeo = RegPersonsGeo.objects.filter(
                    person=appuser.reg_person.id, is_void=False)

                if regpersonsgeo:
                    for regpersongeo in regpersonsgeo:
                        area_ids.append(regpersongeo.area_id)
                print('AREAS', area_ids, appuser.reg_person.id)

                if area_ids:
                    # print 'Non-national users ..'
                    # Get RegPersonsOrgUnits
                    regpersonorgunits = RegPersonsOrgUnits.objects.filter(
                        person=appuser.reg_person.id, is_void=False)
                    for regpersonorgunit in regpersonorgunits:
                        orgunits.append(regpersonorgunit.org_unit_id)

                    # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI', 'TNCI',
                    # 'TNRH', 'TNRC']
                    regorgunits = RegOrgUnit.objects.filter(
                        org_unit_type_id__in=ou_types,
                        id__in=orgunits, is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append(
                            {'id': regorgunit.id,
                             'org_unit_name': str(regorgunit.org_unit_name)})
                    if not regorgunits:
                        # if blank check in services charter if OU provides residential care
                        regservices = RegOrgUnitsService.objects.filter(
                            org_unit_id__in=orgunits, service_id='SCRC',
                            is_void=False)
                        for regservice in regservices:
                            jsonOrgUnitsResults.append(
                                {'id': regservice.org_unit_id,
                                 'org_unit_name': str(regservice.org_unit.org_unit_name)})
                else:
                    # print 'National users (DCS) ..'
                    regorgunits = RegOrgUnit.objects.filter(
                        org_unit_type_id__in=ou_types, is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append(
                            {'id': regorgunit.id,
                             'org_unit_name': str(regorgunit.org_unit_name)})

                    if not regorgunits:
                        # if blank check in services charter if OU provides residential care
                        regservices = RegOrgUnitsService.objects.filter(
                            org_unit_id__in=orgunits, service_id='SCRC',
                            is_void=False)
                        for regservice in regservices:
                            jsonOrgUnitsResults.append(
                                {'id': regservice.org_unit_id,
                                 'org_unit_name': str(regservice.org_unit.org_unit_name)})
            if types == 4:
                # This will be used for Adoption Societies
                # org_unit_types = ['TNSA']
                org_unit_types = ['TNSA', 'TNSI', 'TNCI', 'TNRH', 'TNRC',
                                  'TNAP', 'TNRR', 'TNRB', 'TNRS']
                orgunits = []

                # Get RegPersonsGeo
                area_ids = []
                regpersonsgeo = RegPersonsGeo.objects.filter(
                    person=appuser.reg_person.id, is_void=False)

                if regpersonsgeo:
                    for regpersongeo in regpersonsgeo:
                        area_ids.append(regpersongeo.area_id)

                if area_ids:
                    # print 'Non-national users ..'
                    # Get RegPersonsOrgUnits
                    regpersonorgunits = RegPersonsOrgUnits.objects.filter(
                        person=appuser.reg_person.id, is_void=False)
                    for regpersonorgunit in regpersonorgunits:
                        orgunits.append(regpersonorgunit.org_unit_id)

                    # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI', 'TNCI',
                    # 'TNRH', 'TNRC']
                    regorgunits = RegOrgUnit.objects.filter(
                        id__in=orgunits, org_unit_type_id__in=org_unit_types, is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append({'id': regorgunit.id,
                                                    'org_unit_name': str(regorgunit.org_unit_name)})
                else:
                    # print 'National users (DCS) ..'
                    # Get RegPersonsOrgUnits  - ALL
                    regpersonorgunits = RegPersonsOrgUnits.objects.filter(
                        is_void=False)

                    if regpersonorgunits:
                        for regpersonorgunit in regpersonorgunits:
                            orgunits.append(regpersonorgunit.org_unit_id)

                        # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI',
                        # 'TNCI', 'TNRH', 'TNRC']
                        regorgunits = RegOrgUnit.objects.filter(
                            id__in=orgunits, org_unit_type_id__in=org_unit_types, is_void=False)

                    else:
                        # Get RegOrgUnit org_unit_ids = ['TNSA', 'TNSI',
                        # 'TNCI', 'TNRH', 'TNRC']
                        regorgunits = RegOrgUnit.objects.filter(
                            org_unit_type_id__in=org_unit_types, is_void=False)

                    """ Generate JSON """
                    for regorgunit in regorgunits:
                        jsonOrgUnitsResults.append({'id': regorgunit.id,
                                                    'org_unit_name': str(regorgunit.org_unit_name)})

    except Exception as e:
        raise e
    return JsonResponse(jsonOrgUnitsResults, content_type='application/json',
                        safe=False)


def usersubcounty_lookup(request):
    # For JSON lookup stuff on Case Geo Locs pages
    try:
        if request.method == 'POST':
            user_id = request.POST.get('user_id')
            jsonSubcountyResults = []
            subcounty_ids = []

            user_geolocs = CPOVCUserRoleGeoOrg.objects.filter(
                user_id=int(user_id))
            if user_geolocs:
                # If User Is Attached (Not National Coverage)
                for user_geoloc in user_geolocs:
                    if user_geoloc.area:
                        subcounty_ids.append(int(user_geoloc.area.area_id))
            else:
                # National Coverage
                user_nationalgeolocs = SetupGeography.objects.filter(
                    area_type_id='GDIS')
                for user_geoloc in user_nationalgeolocs:
                    subcounty_ids.append(int(user_geoloc.area_id))

            for subcounty_id in subcounty_ids:
                jsonSubcountyResults.append({'area_id': subcounty_id,
                                             'area_name': translate_geo(subcounty_id)})
    except Exception as e:
        raise e
    return JsonResponse(jsonSubcountyResults, content_type='application/json',
                        safe=False)


def userward_lookup(request):
    # For JSON lookup stuff on Case Geo Locs pages
    try:
        if request.method == 'POST':
            subcounty = request.POST.get('subcounty')

            jsonWardResults = []

            user_geolocs = SetupGeography.objects.filter(
                parent_area_id=int(subcounty))
            for user_geoloc in user_geolocs:
                jsonWardResults.append({'area_id': user_geoloc.area_id,
                                        'area_name': translate_geo(user_geoloc.area_id)})
    except Exception as e:
        raise e
    return JsonResponse(jsonWardResults, content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def forms_home(request):
    '''
    Some default page for forms home page
    '''
    try:
        form = OVCSearchForm(initial={'person_type': 'TBVC'})
        return render(request, 'forms/forms_index.html',
                      {'status': 200,
                       'form': form})
    except Exception as e:
        raise e


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def forms_registry(request):
    form_type = ''
    try:
        if request.method == 'POST':
            # user_id = request.user.id
            # Get logged user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id
            reg_person_id = app_user.reg_person_id
            form_type = request.POST.get('form_type')
            case_serial = request.POST.get('case_serial')

            form = SearchForm(data=request.POST)
            check_fields = ['sex_id', 'case_category_id']
            vals = get_dict(field_name=check_fields)

            person_type = 'TBVC'
            search_string = request.POST.get('form_person')
            search_criteria = 'PSNM'
            number_of_results = 1000
            type_of_person = [person_type] if person_type else []
            include_died = False
            personsets, pids = [], []
            if case_serial:
                print('Case Serial', case_serial)
            pids = get_person_ids(request, search_string)
            personsets = RegPerson.objects.filter(id__in=pids)
            '''
            personsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)
            '''
            if not personsets:
                msg = 'No results for (%s).Name does not exist in database.' % search_string
                messages.add_message(request, messages.ERROR, msg)
                return render(request, 'forms/forms_registry.html', {'form': form, 'form_type': form_type})

            # Lets start from a NULL resultsets
            resultsets = []

            # Child Protection Case
            if form_type == 'FTPC':
                person_ids = []
                # 1. Get Person IDs
                if pids:
                    person_ids = pids
                else:
                    for person in personsets:
                        person_ids.append(int(person.id))
                print('Get Person IDs (%s)... ' % person_ids)
                ovccaserecords_queryset = OVCCaseRecord.objects.filter(
                    person_id__in=person_ids, is_void=False)
                if case_serial:
                    ovccaserecords_queryset = ovccaserecords_queryset.filter(
                        case_serial=case_serial)

                case_ids = []
                # Filter those created by this user
                cases = ovccaserecords_queryset.filter(created_by=user_id)
                for case in cases:
                    case_ids.append(case.case_id)

                # 2. Get OrgUnit(s) of Logged User
                # userorgunit_reported_caseids = []
                loggeduser_orgunitids = []
                loggeduser_regpersonorgunits = RegPersonsOrgUnits.objects.filter(
                    person=reg_person_id, is_void=False)
                for loggeduser_regpersonorgunit in loggeduser_regpersonorgunits:
                    if not loggeduser_regpersonorgunit.org_unit_id in loggeduser_orgunitids:
                        loggeduser_orgunitids.append(
                            loggeduser_regpersonorgunit.org_unit_id)

                # transfers_queryset = OVCCaseEventClosure.objects.all()
                transfers_queryset = OVCCaseEventClosure.objects.exclude(
                    transfer_to_id__isnull=True)
                if loggeduser_orgunitids:
                    ovccasegeos = OVCCaseGeo.objects.filter(
                        report_orgunit__in=loggeduser_orgunitids, person__in=person_ids, is_void=False)

                    if ovccasegeos:
                        for ovccasegeo in ovccasegeos:
                            case_ids.append(str(ovccasegeo.case_id_id))
                            # userorgunit_reported_caseids.append(str(ovccasegeo.case_id_id))
                    # print 'Get Cases from OrgUnit(s) of Logged User ... '

                    # 3. Get Cases Transfered to Logged User OrgUnits
                    transfer_to_orgunits = []
                    if transfers_queryset:
                        transfers = transfers_queryset.filter(
                            transfer_to__in=loggeduser_orgunitids, is_active=True, is_void=False)

                        if transfers:
                            for transfer in transfers:
                                transfer_to_orgunits.append(
                                    transfer.transfer_to_id)
                                ovccaseevents = OVCCaseEvents.objects.filter(
                                    case_event_id=transfer.case_event_id_id, is_void=False)
                                if ovccaseevents:
                                    for ovccaseevent in ovccaseevents:
                                        ovccaserecords = ovccaserecords_queryset.filter(
                                            case_id=ovccaseevent.case_id_id, person__in=person_ids, is_void=False)
                                        if ovccaserecords:
                                            for ovccaserecord in ovccaserecords:
                                                case_ids.append(
                                                    str(ovccaserecord.case_id))
                                            # userorgunit_transfered_caseids.append(str(ovccaserecord.case_id))
                    # print 'Get Cases Transfered to Logged User OrgUnits ... '
                else:
                    '''
                    cases = []
                    ovccasegeos = OVCCaseGeo.objects.filter(
                        person__in=person_ids, is_void=False)
                    if ovccasegeos:
                        for ovccasegeo in ovccasegeos:
                            cases.append(str(ovccasegeo.case_id_id))
                    '''
                    cases = ovccaserecords_queryset.filter(person_id__in=person_ids)
                    for ovccase in cases:
                        case_ids.append(str(ovccase.case_id))

                    print('Get All Case for SuperUsers/Administrator/National Level WFC ... ')
                # Get case categories and geo locations
                case_cats = {}
                case_locs = {}
                case_orgs = {}
                case_cats_qs = OVCCaseCategory.objects.filter(
                    case_id_id__in=case_ids)
                case_locs_qs = OVCCaseGeo.objects.filter(
                    case_id_id__in=case_ids)
                # print 'categories', vals
                for ccat in case_cats_qs:
                    cc_id = ccat.case_id_id
                    cat_id = ccat.case_category
                    case_cat = vals[cat_id] if cat_id in vals else cat_id
                    if cc_id in case_cats:
                        case_cats[cc_id].append(case_cat)
                    else:
                        case_cats[cc_id] = [case_cat]
                for cloc in case_locs_qs:
                    cc_id = cloc.case_id_id
                    sc = cloc.occurence_subcounty
                    case_orgs[cc_id] = cloc.report_orgunit.org_unit_name
                    case_locs[cc_id] = sc.area_name if sc else None

                # 4. Generate Case Status - TRANSFERRED/ACTIVE
                # print 'Next step'
                # 5. Exclude cases transferred from logged user org_unit
                transfered_caseids = []
                transfer_ids = []
                case_event_ids = []
                if transfers_queryset:
                    for transfer in transfers_queryset:
                        transfer_ids.append(transfer.case_event_id_id)

                    ovccaseevents = OVCCaseEvents.objects.filter(
                        case_event_id__in=transfer_ids, is_void=False)
                    if ovccaseevents:
                        for ovccaseevent in ovccaseevents:
                            case_event_ids.append(ovccaseevent.case_id_id)

                        ovccaserecords = ovccaserecords_queryset.filter(
                            case_id__in=case_event_ids,
                            person__in=person_ids, is_void=False)
                        if ovccaserecords:
                            for ovccaserecord in ovccaserecords:
                                transfered_caseids.append(
                                    str(ovccaserecord.case_id))

                    for transfered_caseid in transfered_caseids:
                        if transfered_caseid in case_ids:
                            case_ids.remove(transfered_caseid)

                # 6. Generate resultsets
                # print 'Next Step 1'
                creators = []
                rs_sets = []
                for person in person_ids:
                    print('PERS', person, request.user.get_username())
                    ovc_caserecords = ovccaserecords_queryset.filter(
                        case_id__in=case_ids, is_void=False, person=person)
                    if ovc_caserecords:
                        for ovc_caserecord in ovc_caserecords:
                            print('Found case', ovc_caserecord.person_id)
                            regperson = ovc_caserecord.person
                            creator_id = ovc_caserecord.created_by
                            if creator_id not in creators:
                                creators.append(creator_id)
                            # Add Person Attributes ###
                            setattr(ovc_caserecord, 'id', str(regperson.id))
                            setattr(ovc_caserecord, 'first_name',
                                    str(regperson.first_name))
                            setattr(ovc_caserecord, 'surname',
                                    str(regperson.surname))
                            setattr(ovc_caserecord, 'sex_id',
                                    str(regperson.sex_id))
                            setattr(ovc_caserecord, 'dob',
                                    regperson.date_of_birth)
                            setattr(ovc_caserecord, 'age',
                                    str(regperson.age))
                            setattr(ovc_caserecord, 'form_id', str(
                                ovc_caserecord.case_id).replace('-', ''))
                        rs_sets.append(ovc_caserecords)
                all_users = {}
                # print 'Next Step 2'
                app_users = AppUser.objects.filter(id__in=creators)
                for app_user in app_users:
                    fname = app_user.reg_person.first_name
                    sname = app_user.reg_person.surname
                    onames = app_user.reg_person.other_names
                    oname = onames if onames else ''
                    names = '%s %s %s' % (fname, sname, oname)
                    all_users[app_user.id] = names
                for rss in rs_sets:
                    for rs in rss:
                        cid = rs.case_id
                        uid = rs.created_by
                        case_cat = case_cats[cid] if cid in case_cats else []
                        case_org = case_orgs[cid] if cid in case_orgs else 'BLANK'
                        case_loc = case_locs[cid] if cid in case_locs else 'BLANK'
                        case_user = all_users[uid] if uid in all_users else uid
                        cases_cat = ' ,'.join(case_cat)
                        setattr(rs, 'case_category', cases_cat)
                        setattr(rs, 'org_unit', case_org)
                        setattr(rs, 'case_location', case_loc)
                        setattr(rs, 'case_creator', case_user)
                    resultsets.append(rss)

            # Residential Placement
            elif form_type == 'FTRI':
                person_ids, placement_ids = [], []
                for person in personsets:
                    person_ids.append(int(person.id))
                print('INST', person_ids)

                # Get attached org units
                ou_attached = request.session.get('ou_attached', 0)
                ou_parts = ou_attached.split(',') if ou_attached else []
                ous = [int(iou) for iou in ou_parts] if ou_attached else []
                if request.user.is_active and request.user.is_superuser:
                    ovc_placements = OVCPlacement.objects.filter(
                        person_id__in=person_ids, is_void=False)
                else:
                    ovc_placements = OVCPlacement.objects.filter(
                        residential_institution_id__in=ous,
                        person_id__in=person_ids, is_void=False)

                # Get unique placement ids
                for ovc_placement in ovc_placements:
                    placement_ids.append(ovc_placement.placement_id)
                # Filter transfers and adverse events by placement IDs
                advevents, discharges, transfers = {}, {}, {}
                escapes, abducts = {}, {}
                # 1. Check If Discharged | OVCDischargeFollowUp
                ovc_discharges = OVCDischargeFollowUp.objects.filter(
                    placement_id_id__in=placement_ids, is_void=False)
                for ovc_discharge in ovc_discharges:
                    tid = ovc_discharge.discharge_destination
                    transfer_id = int(tid) if tid else 0
                    discharges[ovc_discharge.placement_id_id] = True
                    transfers[ovc_discharge.placement_id_id] = transfer_id
                # 2. Check if died | OVCAdverseEventsFollowUp
                ovc_adverseevents = OVCAdverseEventsFollowUp.objects.filter(
                    placement_id_id__in=placement_ids, is_void=False)
                for ovc_adverseevent in ovc_adverseevents:
                    ad_event = ovc_adverseevent.adverse_condition_description
                    DEAD = True if 'AEDE' in ad_event else False
                    ESCAPE = True if 'AEES' in ad_event else False
                    ABDUCT = True if 'AEAB' in ad_event else False
                    advevents[ovc_adverseevent.placement_id_id] = DEAD
                    escapes[ovc_adverseevent.placement_id_id] = ESCAPE
                    abducts[ovc_adverseevent.placement_id_id] = ABDUCT
                for ovc_placement in ovc_placements:
                    regperson = ovc_placement.person
                    pid = ovc_placement.placement_id
                    DISCH = discharges[pid] if pid in discharges else False
                    TRANS = transfers[pid] if pid in transfers else 0
                    DEAD = advevents[pid] if pid in advevents else False
                    ESCAPE = escapes[pid] if pid in escapes else False
                    ABDUCT = abducts[pid] if pid in abducts else False
                    # Add Person Attributes ###
                    setattr(ovc_placement, 'id', str(regperson.id))
                    setattr(
                        ovc_placement, 'first_name', str(regperson.first_name))
                    setattr(ovc_placement, 'surname', str(regperson.surname))
                    setattr(ovc_placement, 'sex_id', str(regperson.sex_id))
                    setattr(ovc_placement, 'institution_id',
                            ovc_placement.residential_institution_name)
                    setattr(ovc_placement, 'discharged', DISCH)
                    setattr(ovc_placement, 'transfered', TRANS)
                    setattr(ovc_placement, 'dead', DEAD)
                    setattr(ovc_placement, 'escaped', ESCAPE)
                    setattr(ovc_placement, 'abducted', ABDUCT)
                    setattr(ovc_placement, 'form_id', str(
                        ovc_placement.placement_id).replace('-', ''))
                resultsets.append(ovc_placements)

            # Family Care
            elif form_type == 'FTFC':
                for person in personsets:
                    ovc_familycares = OVCFamilyCare.objects.filter(
                        person=int(person.id), is_void=False)
                    for ovc_familycare in ovc_familycares:
                        regperson = RegPerson.objects.get(
                            pk=ovc_familycare.person_id)
                        # ## Add Person Attributes ###
                        setattr(ovc_familycare, 'id', str(regperson.id))
                        setattr(
                            ovc_familycare, 'first_name', str(regperson.first_name))
                        setattr(
                            ovc_familycare, 'surname', str(regperson.surname))
                        setattr(
                            ovc_familycare, 'sex_id', str(regperson.sex_id))

                        setattr(ovc_familycare, 'form_id', str(
                            ovc_familycare.familycare_id).replace('-', ''))
                    resultsets.append(ovc_familycares)

            # PlacementBackground Details
            elif form_type == 'FTCB':
                for person in personsets:
                    ovc_educations = OVCEducationFollowUp.objects.filter(
                        person=int(person.id), is_void=False)
                    ovc_bursarys = OVCBursary.objects.filter(
                        person=int(person.id), is_void=False)

                    for ovc_education in ovc_educations:
                        regperson = RegPerson.objects.get(
                            pk=ovc_education.person_id)
                        ### Add Person Attributes ###
                        setattr(ovc_education, 'id', str(regperson.id))
                        setattr(ovc_education, 'first_name',
                                str(regperson.first_name))
                        setattr(ovc_education, 'surname',
                                str(regperson.surname))
                        setattr(ovc_education, 'sex_id', str(regperson.sex_id))
                        setattr(ovc_education, 'education_followup_id', str(
                            ovc_education.education_followup_id).replace('-', ''))

                        if ovc_bursarys:
                            setattr(ovc_education, 'has_bursary', 'TRUE')
                            for ovc_bursary in ovc_bursarys:
                                setattr(ovc_education, 'bursary_type', str(
                                    translate(ovc_bursary.bursary_type)))
                                setattr(ovc_education, 'amount',
                                        str(ovc_bursary.amount))
                                setattr(ovc_education, 'bursary_id', str(
                                    ovc_bursary.person_id).replace('-', ''))
                        else:
                            setattr(ovc_education, 'has_bursary', None)
                            setattr(ovc_education, 'bursary_type', None)
                            setattr(ovc_education, 'amount', None)
                            setattr(ovc_education, 'bursary_id', None)
                    resultsets.append(ovc_educations)

            # CSI Form
            elif form_type == 'FCSI':
                for person in personsets:
                    csi_data = OVCCareEvents.objects.filter(person=int(person.id), event_type_id='FCSI', is_void=False)
                    if csi_data:
                        for csi in csi_data:
                            regperson = RegPerson.objects.get(pk=csi.person_id)
                            ### Add Person Attributes ###
                            setattr(csi, 'id', str(regperson.id))
                            setattr(csi, 'first_name', str(regperson.first_name))
                            setattr(csi, 'surname', str(regperson.surname))
                            setattr(csi, 'sex_id', str(regperson.sex_id))
                            setattr(csi, 'form_id', str(csi.event).replace('-', ''))
                            setattr(csi, 'date_of_csi', csi.date_of_event)
                    resultsets.append(csi_data)

            # Services & Moitoring(F1A Form)
            elif form_type == 'FSAM':
                for person in personsets:
                    csi_data = OVCCareEvents.objects.filter(person=int(person.id), event_type_id='FSAM', is_void=False)
                    if csi_data:
                        for csi in csi_data:
                            regperson = RegPerson.objects.get(pk=csi.person_id)
                            ### Add Person Attributes ###
                            setattr(csi, 'id', str(regperson.id))
                            setattr(csi, 'first_name', str(regperson.first_name))
                            setattr(csi, 'surname', str(regperson.surname))
                            setattr(csi, 'sex_id', str(regperson.sex_id))
                            setattr(csi, 'form_id', str(csi.event).replace('-', ''))
                            setattr(csi, 'date_of_f1a', csi.date_of_event)
                    resultsets.append(csi_data)

            # HHVA
            elif form_type == 'FHSA':
                for person in personsets:
                    household_id = None
                    try:        
                        ovcreg = get_object_or_404(OVCRegistration, person=int(person.id), is_void=False)
                        if ovcreg:
                            caretaker_id = ovcreg.caretaker_id if ovcreg else None
                            ovchh = get_object_or_404(OVCHouseHold, head_person=caretaker_id, is_void=False)
                            household_id = ovchh.id if ovchh else None
                    except Exception as e:
                        print(str(e))
                    
                    hhva_data = OVCCareEvents.objects.filter(house_hold=household_id, event_type_id='FHSA', is_void=False)
                    if hhva_data:
                        for hhva in hhva_data:
                            regperson = RegPerson.objects.get(pk=person.id)
                            ### Add Person Attributes ###
                            setattr(hhva, 'id', str(regperson.id))
                            setattr(hhva, 'first_name', str(regperson.first_name))
                            setattr(hhva, 'surname', str(regperson.surname))
                            setattr(hhva, 'sex_id', str(regperson.sex_id))
                            setattr(hhva, 'form_id', str(hhva.event).replace('-', ''))
                            setattr(hhva, 'date_of_hhva', hhva.date_of_event)
                    resultsets.append(hhva_data)
                print('resultsets : %s' %resultsets)

            else:
                msg = 'No ' + \
                    translate(
                        form_type) + ' results found for (%s). Form does not exist.' % search_string
                messages.add_message(request, messages.ERROR, msg)
                return render(request, 'forms/forms_registry.html', {'form': form, 'form_type': form_type})

            # Default Success Message
            msg = 'Showing ' + \
                translate(form_type) + ' results for (%s)' % search_string
            messages.add_message(request, messages.INFO, msg)
            return render(request, 'forms/forms_registry.html',
                          {'form': form, 'resultsets': resultsets, 'vals': vals, 'form_type': form_type})

    except Exception as e:
        msg = 'Forms Search error - %s' % (str(e))
        messages.add_message(request, messages.ERROR, msg)

    form = SearchForm()
    cpims_id = request.GET.get('cpims_id', False)
    if cpims_id:
        resultsets, rs_sets = [], []
        form_type = 'FTPC'
        check_fields = ['sex_id', 'case_category_id']
        vals = get_dict(field_name=check_fields)
        form = SearchForm(initial={'form_type': form_type})
        results = OVCCaseRecord.objects.filter(person_id=cpims_id)
        case_ids = results.values_list('case_id')
        creators = results.values_list('created_by')
        # Related
        case_cats = {}
        case_locs = {}
        case_orgs = {}
        all_users = {}
        app_users = AppUser.objects.filter(id__in=creators)
        for app_user in app_users:
            fname = app_user.reg_person.first_name
            sname = app_user.reg_person.surname
            onames = app_user.reg_person.other_names
            oname = onames if onames else ''
            names = '%s %s %s' % (fname, sname, oname)
            all_users[app_user.id] = names
        case_cats_qs = OVCCaseCategory.objects.filter(
            case_id_id__in=case_ids)
        case_locs_qs = OVCCaseGeo.objects.filter(
            case_id_id__in=case_ids)
        # print 'categories', vals
        for ccat in case_cats_qs:
            cc_id = ccat.case_id_id
            cat_id = ccat.case_category
            case_cat = vals[cat_id] if cat_id in vals else cat_id
            if cc_id in case_cats:
                case_cats[cc_id].append(case_cat)
            else:
                case_cats[cc_id] = [case_cat]
        for cloc in case_locs_qs:
            cc_id = cloc.case_id_id
            sc = cloc.occurence_subcounty
            case_orgs[cc_id] = cloc.report_orgunit.org_unit_name
            case_locs[cc_id] = sc.area_name if sc else None
        print('case ids', case_ids)
        for result in results:
            # Add Person Attributes ###
            rp = result.person
            setattr(result, 'id', str(rp.id))
            setattr(result, 'first_name', str(rp.first_name))
            setattr(result, 'surname', str(rp.surname))
            setattr(result, 'sex_id', str(rp.sex_id))
            setattr(result, 'dob', rp.date_of_birth)
            setattr(result, 'age', str(rp.age))
            setattr(result, 'form_id', str(result.pk).replace('-', ''))
            resultsets.append(result)

        # Add dependencies
        for rs in resultsets:
            cid = rs.case_id
            uid = rs.created_by
            case_cat = case_cats[cid] if cid in case_cats else []
            case_org = case_orgs[cid] if cid in case_orgs else 'BLANK'
            case_loc = case_locs[cid] if cid in case_locs else 'BLANK'
            case_user = all_users[uid] if uid in all_users else uid
            cases_cat = ' ,'.join(case_cat)
            setattr(rs, 'case_category', cases_cat)
            setattr(rs, 'org_unit', case_org)
            setattr(rs, 'case_location', case_loc)
            setattr(rs, 'case_creator', case_user)
        # resultsets.append(rs)
        return render(
            request, 'forms/forms_registry.html',
            {'form': form, 'resultsets': [resultsets],
             'vals': vals, 'form_type': form_type})
    return render(request, 'forms/forms_registry.html', {'form': form})


@login_required
@is_allowed_groups(['DUU'])
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def documents_manager_search(request):
    resultsets = None
    resultset = None
    result = None
    wfc_type = None
    person_type = None
    search_location = False
    search_wfc_by_org_unit = False
    try:
        if request.method == 'POST':
            form = DocumentsManager(data=request.POST)
            check_fields = ['sex_id', 'cadre_type_id', 'person_type_id',
                            'relationship_type_id', 'identifier_type_id']
            vals = get_dict(field_name=check_fields)

            person_type = request.POST.get('person_type')
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')

            # Preselect PersonType selection mandatory
            if person_type:
                wfc_type = 'TBVC'

            # Filter Location Searches
            if search_criteria == 'ORG':
                search_wfc_by_org_unit = True
            if search_criteria == 'RES':
                search_location = True

            resultsets = get_persons_list(user=request.user, tokens=search_string, wfc_type=wfc_type,
                                          search_location=search_location, search_wfc_by_org_unit=search_wfc_by_org_unit)

            check_fields = ['sex_id', 'cadre_type_id', 'person_type_id',
                            'relationship_type_id', 'identifier_type_id']
            vals = get_dict(field_name=check_fields)

            result_pk = None
            pgeolocs_ = None
            porgs_ = None
            if resultsets:
                for resultset in resultsets:
                    if resultset:
                        for result in resultset:
                            result_pk = result.pk

                            person_types = RegPersonsTypes.objects.filter(
                                person=result_pk)
                            person_geos = RegPersonsGeo.objects.filter(
                                person=result_pk)
                            person_orgs = RegPersonsOrgUnits.objects.filter(
                                person=result_pk)

                            result.ptypes = person_types
                            result.pgeos = person_geos
                            result.porgs = person_orgs

                            for person_geo in person_geos:
                                pgeolocs_ = get_vgeo_list(person_geo.area_id)

                            for person_org in person_orgs:
                                porgs_ = get_vorg_list(
                                    person_org.org_unit_id)

                            result.pgeolocs = pgeolocs_
                            result.porgs = porgs_
            return render(request, 'forms/documents_manager.html',
                          {'form': form, 'resultsets': resultsets, 'vals': vals, 'person_type': person_type})
        else:
            print('Not POST')
    except Exception as e:
        msg = 'DocumentsManager Child/Person Search Error - %s' % (str(e))
        messages.add_message(request, messages.INFO, msg)
        return HttpResponseRedirect(reverse(ovc_search))
    form = DocumentsManager()
    return render(request, 'forms/documents_manager.html', {'form': form})


@login_required
@is_allowed_groups(['DUU'])
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def documents_manager(request):
    try:
        if request.method == 'POST':
            document_dest_dir = settings.DOCUMENTS_URL
            person_id = request.POST.get('person')
            document_type = request.POST.get(
                'document_type')
            document_description = request.POST.get(
                'document_description')
            file_name = request.POST.get(
                'file_name')
            file_contents = request.FILES.get(
                'file_browser')

            # Read FileContents
            file_rand = random.randint(100000, 999999)
            now = timezone.now()
            dest_file_name = file_name + '_' + \
                str(file_rand) + '_person_' + str(person_id)
            full_path = document_dest_dir + '/' + dest_file_name
            # full_path = dest_file_name

            # Write Documents to destination
            with open(full_path, 'wb+') as destination:
                for chunk in file_contents.chunks():
                    destination.write(chunk)

            # Save Documents(metadata)
            # document_dir = full_path
            document_name = file_name
            person_id = int(person_id)
            OVCDocuments(
                document_type=document_type,
                document_description=document_description,
                document_name=document_name,
                document_dir=dest_file_name,
                person=RegPerson.objects.get(pk=person_id)).save()
            msg = 'Document(s) Save Successfull'
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseRedirect(reverse(documents_manager))
        else:
            print('Not POST')
    except Exception as e:
        msg = 'Document(s) Save Error - %s' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(documents_manager))
    form = DocumentsManager()
    return render(request, 'forms/documents_manager.html', {'form': form})

    return render(request, 'forms/documents_manager.html', {'status': 200, 'form': form})



@login_required
@is_allowed_groups(['RGM', 'RGU', 'DSU', 'STD'])
def case_record_sheet(request):
    form = OVCSearchForm(data=request.POST, initial={'person_type': 'TBVC'})
    check_fields = ['sex_id', 'person_type_id', 'identifier_type_id']
    vals = get_dict(field_name=check_fields)
    if request.method == 'POST':
        resultsets = None
        person_type = None

        try:
            person_type = 'TBVC'
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')
            number_of_results = 1000
            type_of_person = [person_type] if person_type else []
            include_died = False

            resultsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)

            if resultsets:
                for result in resultsets:

                    # Add case_count to result <object>
                    case_count = OVCCaseRecord.objects.filter(
                        person=int(result.id), is_void=False).count()
                    setattr(result, 'case_count', case_count)

                    # Add child_geo to result <object>
                    ovc_persongeos = RegPersonsGeo.objects.filter(
                        person=int(result.id)).values_list(
                        'area_id', flat=True).order_by('area_id')
                    geo_locs = []
                    for ovc_persongeo in ovc_persongeos:
                        area_id = str(ovc_persongeo)
                        geo_locs.append(translate_geo(int(area_id)))

                    persongeos = ', '.join(geo_locs)

                    setattr(result, 'ovc_persongeos', persongeos)

                msg = 'Showing results for (%s)' % search_string
                messages.add_message(request, messages.INFO, msg)
                return render(request, 'forms/case_record_sheet.html',
                              {'form': form,
                               'resultsets': resultsets,
                               'vals': vals,
                               'person_type': person_type})
            else:
                msg = 'No results for (%s).' % (search_string)
                msg += 'Name does not exist in database.'
                messages.add_message(request, messages.ERROR, msg)
        except Exception as e:
            msg = 'OVC search error - %s' % (str(e))
            messages.add_message(request, messages.INFO, msg)
        return HttpResponseRedirect(reverse(case_record_sheet))
    else:
        cpims_id = request.GET.get('cpims_id', False)
        form = OVCSearchForm(initial={'search_criteria': 'NAME'})
        if cpims_id:
            resultsets = RegPerson.objects.filter(id=cpims_id)
            return render(
                request, 'forms/case_record_sheet.html',
                {'form': form, 'resultsets': resultsets,
                 'vals': vals, 'person_type': person_type})
        form = OVCSearchForm(initial={'search_criteria': 'NAME'})
        return render(request, 'forms/case_record_sheet.html',
                      {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_case_record_sheet(request, id):

    # Get logged in user
    username = request.user.get_username()
    app_user = AppUser.objects.get(username=username)
    user_id = request.user.id

    try:
        if request.method == 'POST':
            form = OVC_FT3hForm(data=request.POST)
            now = timezone.now()
            form_id = request.POST.get('case_id')
            person = request.POST.get('person')

            # OVC_Reporting
            case_reporter = request.POST.get('case_reporter')
            court_name = request.POST.get(
                'court_name') if request.POST.get('court_name') else None
            court_number = request.POST.get(
                'court_number') if request.POST.get('court_number') else None
            police_station = request.POST.get(
                'police_station') if request.POST.get('police_station') else None
            ob_number = request.POST.get(
                'ob_number') if request.POST.get('ob_number') else None
            case_reporter_first_name = request.POST.get(
                'case_reporter_first_name') if request.POST.get('case_reporter_first_name') else None
            case_reporter_other_names = request.POST.get(
                'case_reporter_other_names') if request.POST.get('case_reporter_other_names') else None
            case_reporter_surname = request.POST.get(
                'case_reporter_surname') if request.POST.get('case_reporter_surname') else None
            case_reporter_contacts = request.POST.get(
                'case_reporter_contacts') if request.POST.get('case_reporter_contacts') else None

            date_case_opened = request.POST.get('date_case_opened')
            if date_case_opened:
                date_case_opened = convert_date(date_case_opened)

            # OVCCaseGeo
            report_subcounty = request.POST.get('report_subcounty')
            report_ward = request.POST.get('report_ward')
            report_village = request.POST.get('report_village')
            report_orgunit = request.POST.get('report_orgunit')
            occurence_county = request.POST.get('occurence_county')
            occurence_subcounty = request.POST.get('occurence_subcounty')
            occurence_ward = request.POST.get('occurence_ward')
            occurence_village = request.POST.get('occurence_village')

            # Added for CTiP and Locations handling
            occurence_nationality = request.POST.get('occurence_nationality')
            occurence_country = request.POST.get('occurence_country')
            occurence_city = request.POST.get('occurence_city')
            occurence_location = request.POST.get('occurence_location')
            occurence_sublocation = request.POST.get('occurence_sublocation')

            # OVC_Details
            person = request.POST.get('person')
            hh_economic_status = request.POST.get('household_economics')
            family_status = request.POST.getlist('family_status')
            hobbies = request.POST.get('hobbies')
            friends = request.POST.get('friends')

            # OVC_Medical_SubConditions
            mental_subconditions = request.POST.getlist('mental_subcondition')
            physical_subconditions = request.POST.getlist(
                'physical_subcondition')
            other_subconditions = request.POST.getlist('other_subcondition')

            # OVC_Medical
            mental_condition = request.POST.get('mental_condition')
            physical_condition = request.POST.get('physical_condition')
            other_condition = request.POST.get('other_condition')

            # OVC_CaseRecord
            serial_number = request.POST.get('serial_number')
            perpetrator_status = request.POST.get(
                'perpetrator_status') if request.POST.get('perpetrator_status') else None
            perpetrator_first_name = request.POST.get(
                'perpetrator_first_name') if request.POST.get('perpetrator_first_name') else None
            perpetrator_other_names = request.POST.get(
                'perpetrator_other_names') if request.POST.get('perpetrator_other_names') else None
            perpetrator_surname = request.POST.get(
                'perpetrator_surname') if request.POST.get('perpetrator_surname') else None
            perpetrator_relationship = request.POST.get(
                'perpetrator_relationship') if request.POST.get('perpetrator_relationship') else None
            # place_of_event = request.POST.get('place_of_event')
            # case_nature = request.POST.get('case_nature')
            risk_level = request.POST.get('risk_level')
            immediate_needs = request.POST.getlist('immediate_needs')
            future_needs = request.POST.getlist('future_needs')
            case_remarks = request.POST.get('case_remarks')
            refferal_to = request.POST.getlist('refferal_to')
            refferal_present = request.POST.get('refferal_present')
            summon_issued = request.POST.get('summon_issued')
            summon_status = False if summon_issued == 'AYES' else None
            date_of_summon = request.POST.get('date_of_summon')
            if date_of_summon:
                date_of_summon = convert_date(date_of_summon)
            else:
                date_of_summon = None

            # OVCCaseRecord
            ovccr = OVCCaseRecord.objects.get(case_id=id)
            cid = ovccr.case_id
            pers_id = ovccr.person_id
            ovccr.case_serial = validate_serialnumber(
                pers_id, report_subcounty, serial_number)
            #ovccr.place_of_event = place_of_event
            ovccr.perpetrator_status = perpetrator_status
            ovccr.perpetrator_first_name = perpetrator_first_name.upper(
            ) if perpetrator_first_name else None
            ovccr.perpetrator_other_names = perpetrator_other_names.upper(
            ) if perpetrator_other_names else None
            ovccr.perpetrator_surname = perpetrator_surname.upper() if perpetrator_surname else None
            #ovccr.case_nature = case_nature
            ovccr.risk_level = risk_level
            ovccr.date_case_opened = date_case_opened
            ovccr.case_reporter = case_reporter
            ovccr.court_name = court_name if court_name else None
            ovccr.court_number = court_number if court_number else None
            ovccr.police_station = police_station if police_station else None
            ovccr.ob_number = ob_number if ob_number else None
            ovccr.case_reporter_first_name = case_reporter_first_name if case_reporter_first_name else None
            ovccr.case_reporter_surname = case_reporter_surname if case_reporter_surname else None
            ovccr.case_reporter_contacts = case_reporter_contacts if case_reporter_contacts else None
            ovccr.case_status = 'ACTIVE'
            ovccr.case_remarks = case_remarks
            ovccr.referral_present = refferal_present
            ovccr.date_of_summon = date_of_summon if date_of_summon else None
            ovccr.save(update_fields=[  # 'place_of_event',
                'case_serial',
                'perpetrator_first_name',
                'perpetrator_other_names',
                'perpetrator_surname',
                'risk_level',
                'date_case_opened',
                'case_reporter_first_name',
                'case_reporter_surname',
                'case_reporter_contacts',
                'case_reporter',
                'court_name',
                'court_number',
                'police_station',
                'ob_number',
                'case_status',
                'case_remarks',
                'referral_present'])

            # OVCCaseCategory
            case_category_list = request.POST.get('case_category_list')
            new_case_categorys = []
            existing_case_categorys = []

            if case_category_list:
                # Get Existing Case Categories
                existingcasecategorys = OVCCaseCategory.objects.filter(
                    case_id=id, is_void=False)
                for existingcasecategory in existingcasecategorys:
                    existing_case_categorys.append({'case_category': str(existingcasecategory.case_category),
                                                    'case_grouping_id': str(existingcasecategory.case_grouping_id)})

                case_category_data = json.loads(case_category_list)
                for case_categorys in case_category_data:
                    case_category = case_categorys['case_category']
                    date_of_event = case_categorys['date_of_event']
                    if date_of_event:
                        date_of_event = convert_date(date_of_event)
                    place_of_event = case_categorys['place_of_event']
                    case_nature = case_categorys['case_nature']
                    case_grouping_id = case_categorys['case_grouping_id']
                    case_subcategorys = case_categorys['case_subcategory']

                    case_subcategorys = case_subcategorys.split(',')

                    # OVCCaseCategory - NEW
                    if not (case_grouping_id):
                        if case_category:
                            case_grouping_id = new_guid_32()
                            ovccasecategory = OVCCaseCategory(
                                # case_category_id=new_guid_32(),
                                case_id=OVCCaseRecord.objects.get(pk=id),
                                case_grouping_id=case_grouping_id,
                                case_category=case_category.strip(),
                                date_of_event=date_of_event,
                                place_of_event=place_of_event.strip(),
                                case_nature=case_nature.strip(),
                                timestamp_created=now,
                                person=RegPerson.objects.get(pk=int(person))
                            )
                            ovccasecategory.save()
                            new_pk = ovccasecategory.pk

                            # OVCCaseSubCategory - NEW
                            for i, case_subcategory in enumerate(case_subcategorys):
                                OVCCaseSubCategory(
                                    case_category=OVCCaseCategory.objects.get(
                                        pk=new_pk),
                                    case_grouping_id=case_grouping_id,
                                    sub_category_id=case_subcategory.strip(),
                                    timestamp_created=now,
                                    person=RegPerson.objects.get(
                                        pk=int(person))
                                ).save()

                    ## Pool New Cases ###
                    if case_category:
                        new_case_categorys.append({'case_category': case_category.strip(),
                                                   'case_grouping_id': case_grouping_id})

                """ Cater for removed Case Categories """
                ncase_categorys = []
                ncase_grouping_ids = []
                for new_case_category in new_case_categorys:
                    ncasecategory = new_case_category['case_category']
                    ncasegroupingid = new_case_category['case_grouping_id']
                    ncase_categorys.append(str(ncasecategory))
                    ncase_grouping_ids.append(str(ncasegroupingid))

                for existing_case_category in existing_case_categorys:
                    ecasecategory = existing_case_category['case_category']
                    ecase_grouping_id = existing_case_category[
                        'case_grouping_id']
                    if (ecasecategory not in ncase_categorys) or (ecase_grouping_id not in ncase_grouping_ids):
                        # Deleted/Removed OVCCaseCategory
                        ovcexistingcasecategorys = OVCCaseCategory.objects.get(
                            case_grouping_id=ecase_grouping_id)
                        ovcexistingcasecategorys.is_void = True
                        ovcexistingcasecategorys.save(
                            update_fields=['is_void'])

                        # Deleted/Removed OVCCaseSubCategory
                        ovcexistingcasesubcategorys = OVCCaseSubCategory.objects.filter(
                            case_grouping_id=ecase_grouping_id)
                        for ovcexistingcasesubcategory in ovcexistingcasesubcategorys:
                            ovcexistingcasesubcategory.is_void = True
                            ovcexistingcasesubcategory.save(
                                update_fields=['is_void'])
            # Other case geos for CTiP - Country and locations
            geo_params = {}
            geo_params['country'] = occurence_country
            geo_params['city'] = occurence_city
            geo_params['location'] = occurence_location
            geo_params['sub_location'] = occurence_sublocation
            save_case_other_geos(id, pers_id, geo_params)

            # OVCCaseGeo
            ovcgeo = get_case_geo(request, id)
            county_id = int(occurence_county) if occurence_county else None
            sc_id = int(occurence_subcounty) if occurence_subcounty else None
            if ovcgeo:
                # ovcgeo = OVCCaseGeo.objects.get(case_id=id)
                # print 'Update case Geo'
                ovcgeo.report_subcounty = SetupGeography.objects.get(
                    pk=int(report_subcounty))
                ovcgeo.report_ward = report_ward
                ovcgeo.report_village = report_village
                ovcgeo.report_orgunit = RegOrgUnit.objects.get(
                    pk=int(report_orgunit))
                ovcgeo.occurence_county_id = county_id
                ovcgeo.occurence_subcounty_id = sc_id
                ovcgeo.occurence_ward = occurence_ward
                ovcgeo.occurence_village = occurence_village
                ovcgeo.save(update_fields=['report_subcounty',
                                           'report_ward',
                                           'report_village',
                                           'report_orgunit',
                                           'occurence_county',
                                           'occurence_subcounty',
                                           'occurence_ward',
                                           'occurence_village'])
            else:
                print('New case Geo')
                OVCCaseGeo(
                    case_id=OVCCaseRecord.objects.get(pk=id),
                    report_subcounty=SetupGeography.objects.get(
                        pk=int(report_subcounty)),
                    report_ward=report_ward,
                    report_village=report_village,
                    report_orgunit=RegOrgUnit.objects.get(
                        pk=int(report_orgunit)),
                    occurence_county_id=county_id,
                    occurence_subcounty_id=sc_id,
                    occurence_ward=occurence_ward,
                    occurence_village=occurence_village,
                    timestamp_created=now,
                    person_id=pers_id).save()

            # OVCEconomicStatus
            '''
            ovcd = OVCEconomicStatus.objects.get(case_id=id)
            ovcd.household_economic_status = household_economic_status
            ovcd.save(update_fields=['household_economic_status'])
            '''
            ovcd, created = OVCEconomicStatus.objects.update_or_create(
                case_id_id=id, person_id=pers_id,
                defaults={'household_economic_status': hh_economic_status,
                          'is_void': False},)

            # OVCFamilyStatus
            existing_familystata = []
            ovcfamilystata = OVCFamilyStatus.objects.filter(case_id=id)
            for ovcfamilystatus in ovcfamilystata:
                existing_familystata.append(str(ovcfamilystatus.family_status))
            """ Cater for Unchecked yet Pre-existed """
            for i, efamilystatus in enumerate(existing_familystata):
                if not(str(efamilystatus) in family_status):
                    OVCFamilyStatus.objects.filter(
                        family_status=efamilystatus,
                        case_id=id).update(is_void=True)
            """ Cater for new selected refferals """
            for i, nfamily_status in enumerate(family_status):
                if not (str(nfamily_status) in existing_familystata):
                    OVCFamilyStatus(
                        case_id=OVCCaseRecord.objects.get(pk=id),
                        family_status=nfamily_status,
                        person=RegPerson.objects.get(pk=int(person))).save()
            # OVCHobbies
            hobbies_exist = OVCHobbies.objects.filter(case_id=id)
            if hobbies_exist:
                OVCHobbies.objects.filter(case_id=id).update(is_void=True)
            hobbies = str(hobbies).replace('[', '')
            hobbies = str(hobbies).replace(']', '')
            if hobbies:
                hobbies = str(hobbies).split(",")
                for hobby in hobbies:
                    OVCHobbies(
                        case_id=OVCCaseRecord.objects.get(pk=id),
                        hobby=hobby.upper(),
                        timestamp_created=now,
                        person=RegPerson.objects.get(pk=int(person))).save()
            # OVCFriends
            ovcfrnds_exist = OVCFriends.objects.filter(case_id=id)
            if ovcfrnds_exist:
                OVCFriends.objects.filter(case_id=id).update(is_void=True)
            friends = str(friends).replace('[', '')
            friends = str(friends).replace(']', '')
            if friends:
                friends = str(friends).split(",")
                for i, friend in enumerate(friends):
                    names = (friends[i]).split()
                    if(len(names) == 1):
                        ffname = names[0]
                        foname = 'XXXX'
                        fsname = 'XXXX'
                    if(len(names) == 2):
                        ffname = names[0]
                        foname = names[1]
                        fsname = 'XXXX'
                    elif(len(names) == 3):
                        ffname = names[0]
                        foname = names[1]
                        fsname = names[2]
                    OVCFriends(
                        case_id=OVCCaseRecord.objects.get(case_id=id),
                        friend_firstname=ffname.upper(),
                        friend_other_names=foname.upper(),
                        friend_surname=fsname.upper(),
                        timestamp_created=now,
                        person=RegPerson.objects.get(pk=int(person))).save()
            # OVCMedical
            '''
            ovcmed = OVCMedical.objects.get(case_id=id)
            ovcmed.mental_condition = mental_condition
            ovcmed.physical_condition = physical_condition
            ovcmed.other_condition = other_condition
            ovcmed.save(update_fields=['mental_condition',
                                       'physical_condition',
                                       'other_condition'])

            '''
            ovcmed, created = OVCMedical.objects.update_or_create(
                case_id_id=id, person_id=pers_id,
                defaults={'mental_condition': mental_condition,
                          'physical_condition': physical_condition,
                          'other_condition': other_condition,
                          'is_void': False},)

            # OVCMedicalSubconditions
            """ Delete SubConditions if Captured Erroniously """
            med_conditions = []
            medical_id_ = None
            if ovcmed:
                medical_id_ = ovcmed.medical_id

            if not mental_condition == "MNRM":
                OVCMedicalSubconditions.objects.filter(
                    medical_id=medical_id_, medical_condition='Mental').update(is_void=True)

                for i, mental_subcondition in enumerate(mental_subconditions):
                    mental_subcondition = mental_subcondition.split(',')
                    for mcondition in mental_subcondition:
                        OVCMedicalSubconditions(
                            medicalsubcond_id=new_guid_32(),
                            medical_id=OVCMedical.objects.get(pk=medical_id_),
                            medical_condition='Mental',
                            medical_subcondition=mcondition,
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()
            if not physical_condition == "PNRM":
                OVCMedicalSubconditions.objects.filter(
                    medical_id=medical_id_, medical_condition='Physical').update(is_void=True)
                for i, physical_subcondition in enumerate(physical_subconditions):
                    physical_subcondition = physical_subcondition.split(',')
                    for pcondition in physical_subcondition:
                        OVCMedicalSubconditions(
                            medicalsubcond_id=new_guid_32(),
                            medical_id=OVCMedical.objects.get(pk=medical_id_),
                            medical_condition='Physical',
                            medical_subcondition=pcondition,
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()
            if not other_condition == "CHNM":
                OVCMedicalSubconditions.objects.filter(
                    medical_id=medical_id_, medical_condition='Other').update(is_void=True)
                for i, other_subcondition in enumerate(other_subconditions):
                    other_subcondition = other_subcondition.split(',')
                    for ocondition in other_subcondition:
                        OVCMedicalSubconditions(
                            medicalsubcond_id=new_guid_32(),
                            medical_id=OVCMedical.objects.get(pk=medical_id_),
                            medical_condition='Other',
                            medical_subcondition=ocondition,
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()
            # OVCReferral
            referralactors_list = request.POST.get('referralactors_list')
            new_referrals = []
            existing_referrals = []

            if referralactors_list:
                # Get Existing Referrals
                existingreferrals = OVCReferral.objects.filter(
                    case_id=id, is_void=False)
                for existingreferral in existingreferrals:
                    existing_referrals.append({'refferal_to': str(existingreferral.refferal_to),
                                               'referral_grouping_id': str(existingreferral.referral_grouping_id)})

                referralactors_data = json.loads(referralactors_list)
                for referralactors in referralactors_data:
                    refferal_actor_type = referralactors[
                        'refferal_destination_type']
                    referral_actor_description = referralactors[
                        'refferal_destination_description']
                    refferal_to = referralactors['refferal_to']
                    referral_grouping_id = referralactors[
                        'referral_grouping_id']

                    # OVCReferral - NEW
                    if not (referral_grouping_id):
                        if refferal_to:
                            referral_grouping_id = new_guid_32()
                            OVCReferral(
                                case_id=OVCCaseRecord.objects.get(pk=id),
                                refferal_actor_type=refferal_actor_type,
                                refferal_actor_specify=referral_actor_description,
                                refferal_to=refferal_to,
                                referral_grouping_id=referral_grouping_id,
                                case_category=None,
                                timestamp_created=now,
                                person=RegPerson.objects.get(pk=int(person))).save()
                    ## Pool New Referrals ###
                    if refferal_to:
                        new_referrals.append({'refferal_to': refferal_to.strip(),
                                              'referral_grouping_id': referral_grouping_id})

                """ Cater for removed Referrals """
                nreferrals = []
                nreferral_grouping_ids = []
                for new_referral in new_referrals:
                    nrefferal_to = new_referral['refferal_to']
                    nreferralgroupingid = new_referral['referral_grouping_id']
                    nreferrals.append(str(nrefferal_to))
                    nreferral_grouping_ids.append(str(nreferralgroupingid))

                for existing_referral in existing_referrals:
                    erefferal_to = existing_referral['refferal_to']
                    ereferralgroupingid = existing_referral[
                        'referral_grouping_id']

                    if (erefferal_to not in nreferrals):
                        # Deleted/Removed OVCCaseCategory
                        ovcexistingrefferal = OVCReferral.objects.get(
                            referral_grouping_id=ereferralgroupingid)
                        ovcexistingrefferal.is_void = True
                        ovcexistingrefferal.save(update_fields=['is_void'])

            # OVCNeeds
            existing_immediateneeds = []
            ovcimmediateneeds = OVCNeeds.objects.filter(
                case_id=id, need_type='IMMEDIATE')
            for ovcimmediateneed in ovcimmediateneeds:
                existing_immediateneeds.append(str(ovcimmediateneed.need_type))
            """ Cater for Unchecked yet Pre-existed """
            for i, eimmediateneed in enumerate(existing_immediateneeds):
                if not(str(eimmediateneed) in immediate_needs):
                    ovcneedsimmediate = OVCNeeds.objects.filter(
                        case_id=id, need_type=eimmediateneed)
                    for ovcneedimmediate in ovcneedsimmediate:
                        ovcneedimmediate.is_void = True
                        ovcneedimmediate.save(update_fields=['is_void'])
            """ Cater for new selected immediate needs """
            for i, nimmediateneed in enumerate(immediate_needs):
                if not (str(nimmediateneed) in existing_immediateneeds):
                    OVCNeeds(
                        case_id=OVCCaseRecord.objects.get(pk=id),
                        need_description=nimmediateneed.upper(),
                        need_type='IMMEDIATE',
                        timestamp_created=now,
                        person=RegPerson.objects.get(pk=int(person))
                    ).save()

            existing_futureneeds = []
            ovcfutureneeds = OVCNeeds.objects.filter(
                case_id=id, need_type='future')
            for ovcfutureneed in ovcfutureneeds:
                existing_futureneeds.append(str(ovcfutureneed.need_type))
            """ Cater for Unchecked yet Pre-existed """
            for i, efutureneed in enumerate(existing_futureneeds):
                if not(str(efutureneed) in future_needs):
                    ovcneedsfuture = OVCNeeds.objects.filter(
                        case_id=id, need_type=efutureneed)
                    for ovcneedfuture in ovcneedsfuture:
                        ovcneedfuture.is_void = True
                        ovcneedfuture.save(update_fields=['is_void'])
            """ Cater for new selected future needs """
            for i, nfutureneed in enumerate(future_needs):
                if not (str(nfutureneed) in existing_futureneeds):
                    OVCNeeds(
                        case_id=OVCCaseRecord.objects.get(pk=id),
                        need_description=nfutureneed.upper(),
                        need_type='FUTURE',
                        timestamp_created=now,
                        person=RegPerson.objects.get(pk=int(person))
                    ).save()

            # FormsLog
            '''
            f = FormsLog.objects.get(form_id=id)
            f.timestamp_modified = now
            f.save(update_fields=['timestamp_modified'])
            '''
            f, created = FormsLog.objects.update_or_create(
                form_id=id, person_id=pers_id, form_type_id='FTPC',
                defaults={'timestamp_modified': now,
                          'app_user': request.user.id, 'is_void': False},)
        else:
            # Get PersonId/Init Data
            try:
                f = FormsLog.objects.get(form_id=id, is_void=False)
            except Exception:
                f = OVCCaseRecord.objects.get(case_id=id)
            person_id = int(f.person_id)

            # Get Siblings
            init_data = RegPerson.objects.filter(pk=person_id, is_void=False)
            reg_personsiblings = []
            for data in init_data:
                regpersonsiblings = RegPersonsSiblings.objects.filter(
                    child_person=data.id)
                for regpersonsibling in regpersonsiblings:
                    reg_personsiblings.append(regpersonsibling.sibling_person)
            init_data.siblingpersons = reg_personsiblings

            check_fields = [
                'sex_id', 'referral_destination_classification',
                'perpetrator_status_id',
                'case_reporter_id', 'perpetrator_id',
                'long_term_support_id', 'immediate_need_id',
                'relationship_type_id']
            vals = get_dict(field_name=check_fields)

            # Get OVCEconomicStatus
            try:
                results_details = OVCEconomicStatus.objects.get(
                    case_id=id, is_void=False)
            except Exception:
                results_details = None

            # Get OVCMedical
            try:
                results_med = OVCMedical.objects.get(case_id=id, is_void=False)
            except Exception:
                results_med = Myobject()
                results_med.other_condition = ''
                results_med.physical_condition = ''
                results_med.mental_condition = ''
                results_med.medical_id = ''

            # Get OVCMedicalSubconditions
            _physical_subconditions = []
            _mental_subconditions = []
            _other_subconditions = []
            medical_id = results_med.medical_id
            if medical_id:
                results_medsubs = OVCMedicalSubconditions.objects.filter(
                    medical_id=medical_id)
                if results_medsubs:
                    for results_medsub in results_medsubs:
                        if results_medsub.medical_condition == 'Physical':
                            _physical_subconditions.append(
                                results_medsub.medical_subcondition)
                        if results_medsub.medical_condition == 'Mental':
                            _mental_subconditions.append(
                                results_medsub.medical_subcondition)
                        if results_medsub.medical_condition == 'Other':
                            _other_subconditions.append(
                                results_medsub.medical_subcondition)

            # Get OVCCaseRecord
            results_case = OVCCaseRecord.objects.get(case_id=id, is_void=False)
            perpetrators = OvcCasePersons.objects.filter(
                case_id=id, person_type='PERP')
            # Create perpetrator objects
            perps_objs = []
            perp_cnt = 0
            for perp_obj in perpetrators:
                perp_cnt += 1
                pobj = {"relation": "CGOR", "other_relation": "RCFD",
                        "first_name": "James", "surname": "Nyikal",
                        "other_name": "", "item_id": perp_cnt}
                perps_objs.append(pobj)

            # Get OVCCaseGeo
            results_geo = get_case_geo(request, id)

            # CTiP - Get other geos
            report_in_country = 'AYES'
            occurence_country = ''
            occurence_city = ''
            try:
                other_geos = OVCCaseLocation.objects.get(case_id=id)
                occurence_country = other_geos.report_country_code
                occurence_city = other_geos.report_city
                print('Diaspora', occurence_country, occurence_city)
                if occurence_country and occurence_country != 'KE':
                    report_in_country = 'ANNO'
            except Exception as e:
                print('get other geo error - %s' % (str(e)))

            # Get OVCFriends
            results_frnds = OVCFriends.objects.filter(
                case_id=id, is_void=False)
            results_frnd = []
            for result_frnds in results_frnds:
                result_frnds_fname = str(result_frnds.friend_firstname)
                result_frnds_oname = str(result_frnds.friend_other_names)
                result_frnds_lname = str(result_frnds.friend_surname)

                result_frnds_name = result_frnds_fname
                if not result_frnds_oname == 'XXXX':
                    result_frnds_name = result_frnds_name + \
                        ' ' + result_frnds_oname
                if not result_frnds_lname == 'XXXX':
                    result_frnds_name = result_frnds_name + \
                        ' ' + result_frnds_lname
                results_frnd.append(result_frnds_name)

            # Get OVCHobbies
            results_hobs = OVCHobbies.objects.filter(case_id=id, is_void=False)
            results_hob = []
            for result_hobs in results_hobs:
                result_hobs_ = str(result_hobs.hobby)
                results_hob.append(result_hobs_)

            # Get OVCNeeds
            results_imm = []
            results_imm_needs = OVCNeeds.objects.filter(
                case_id=id, need_type='IMMEDIATE', is_void=False)
            for results_imm_need in results_imm_needs:
                results_imm_ = str(results_imm_need.need_description)
                results_imm.append(results_imm_)

            results_fut = []
            results_fut_needs = OVCNeeds.objects.filter(
                case_id=id, need_type='FUTURE', is_void=False)
            for results_fut_need in results_fut_needs:
                results_fut_ = str(results_fut_need.need_description)
                results_fut.append(results_fut_)

            # Get OVCReferral
            # referrals = []
            results_ref = OVCReferral.objects.filter(case_id=id, is_void=False)

            # Get OVCFamilyStatus
            results_family_status = []
            results_familystatus = OVCFamilyStatus.objects.filter(
                case_id=id, is_void=False)
            for result_famstatus in results_familystatus:
                results_family_status.append(result_famstatus.family_status)

            # Get OVCCaseCategory
            case_grouping_ids = []
            jsonCategorysData = []
            jsonSubCategorysData = []
            str_jsonsubcategorydata = ''
            resultsets = []
            ovcccats = OVCCaseCategory.objects.filter(
                case_id=id, is_void=False)
            """ Get case_grouping_ids[] """
            for ovcccat in ovcccats:
                case_grouping_id = str(ovcccat.case_grouping_id)
                if case_grouping_id not in case_grouping_ids:
                    case_grouping_ids.append(str(case_grouping_id))

            """ Get Case Categories """
            ovcccats2 = None
            for case_grouping_id in case_grouping_ids:
                ovcccats2 = OVCCaseCategory.objects.filter(
                    case_grouping_id=case_grouping_id)

                jsonSubCategorysIdData = []
                for ovcccat in ovcccats2:
                    # OVCCaseSubCategory
                    ovccasesubcategorys = OVCCaseSubCategory.objects.filter(
                        case_grouping_id=case_grouping_id)
                    for ovccasesubcategory in ovccasesubcategorys:
                        jsonSubCategorysIdData.append(
                            ovccasesubcategory.sub_category_id)
                        jsonSubCategorysData.append(
                            translate(str(ovccasesubcategory.sub_category_id)))
                    str_jsonsubcategorydata = ','.join(jsonSubCategorysData)
                    str_jsonsubcategoryiddata = ','.join(
                        jsonSubCategorysIdData)

                    jsonCategorysData.append(
                        {'case_category': ovcccat.case_category,
                         'case_subcategorys': str_jsonsubcategorydata,
                         'case_subcategorysids': str_jsonsubcategoryiddata,
                         'date_of_event': (ovcccat.date_of_event).strftime('%d-%b-%Y'),
                         'place_of_event': ovcccat.place_of_event,
                         'case_nature': ovcccat.case_nature,
                         'case_grouping_id': str(ovcccat.case_grouping_id)})
                    jsonSubCategorysData = []

            """ Create resultsets """
            resultsets.append(jsonCategorysData)

            # Retrieve Referrals
            jsonData2 = []
            resultsets2 = []
            referral_grouping_ids = []
            """ Get referral_grouping_ids[] """
            for reffs in results_ref:
                referral_grouping_id = str(reffs.referral_grouping_id)
                if not referral_grouping_id in referral_grouping_ids:
                    referral_grouping_ids.append(str(referral_grouping_id))
            """ Get Referral Actors """
            ovcrefa2 = None
            for referral_grouping_id in referral_grouping_ids:
                ovcrefa2 = OVCReferral.objects.filter(
                    referral_grouping_id=referral_grouping_id)
                for ra in ovcrefa2:
                    jsonData2.append({'refferal_actor_type': translate(ra.refferal_actor_type),
                                      'refferal_actor_type_id': ra.refferal_actor_type,
                                      'refferal_actor_specify': ra.refferal_actor_specify,
                                      'refferal_to': translate(ra.refferal_to),
                                      'refferal_to_id': ra.refferal_to,
                                      'referral_grouping_id': str(ra.referral_grouping_id)
                                      })
            resultsets2.append(jsonData2)

            # Get Summons
            summon_issued = 'ANNO'
            date_of_summon = results_case.date_of_summon
            if date_of_summon:
                date_of_summon = date_of_summon.strftime('%d-%b-%Y')
                summon_issued = 'AYES'

            # Get Subcounty of app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id
            # Missing Geo
            print('result fake')
            if results_geo:
                oc = results_geo.occurence_county
                osc = results_geo.occurence_subcounty
                report_subcounty = results_geo.report_subcounty.area_id
                report_ward = results_geo.report_ward
                report_village = results_geo.report_village
                print('b4', results_geo.report_orgunit)
                # report_orgunit = translate_reverse_org(results_geo.report_orgunit.id)
                report_orgunit = results_geo.report_orgunit.id
                print('r ou', report_orgunit)
                occurence_county = oc.area_id if oc else None
                occurence_subcounty = osc.area_id if osc else None
                occurence_ward = results_geo.occurence_ward
                occurence_village = results_geo.occurence_village
            else:
                report_subcounty, report_ward, report_village = '', '', ''
                report_orgunit, occurence_county, occurence_subcounty = '', '', ''
                occurence_ward, occurence_village = '', ''

            # Initiaize OVC_FT3hForm()
            hh_economic_status = ''
            if results_details:
                hh_economic_status = results_details.household_economic_status
            form = OVC_FT3hForm({
                'person': person_id,
                'user_id': user_id,
                'occurence_nationality': report_in_country,
                'occurence_country': occurence_country,
                'occurence_city': occurence_city,
                # Tab 1
                'case_reporter': results_case.case_reporter,
                'court_name': results_case.court_name,
                'court_number': results_case.court_number,
                'police_station': results_case.police_station,
                'ob_number': results_case.ob_number,
                'case_reporter_first_name': results_case.case_reporter_first_name,
                'case_reporter_other_names': results_case.case_reporter_other_names,
                'case_reporter_surname': results_case.case_reporter_surname,
                'case_reporter_contacts': results_case.case_reporter_contacts,
                'date_case_opened': (results_case.date_case_opened).strftime('%d-%b-%Y'),
                'report_subcounty': report_subcounty,
                'report_ward': report_ward,
                'report_village': report_village,
                'report_orgunit': report_orgunit,
                'occurence_county': occurence_county,
                'occurence_subcounty': occurence_subcounty,
                'occurence_ward': occurence_ward,
                'occurence_village': occurence_village,
                # Tab 2
                'household_economics': hh_economic_status,
                'family_status': results_family_status,
                'friends': results_frnd,
                'hobbies': results_hob,
                # Tab 3
                'mental_condition': results_med.mental_condition,
                'mental_subcondition': _mental_subconditions,
                'physical_condition': results_med.physical_condition,
                'physical_subcondition': _physical_subconditions,
                'other_condition': results_med.other_condition,
                'other_subcondition': _other_subconditions,
                # Tab 4
                'serial_number': results_case.case_serial,
                'perpetrator_status': results_case.perpetrator_status,
                'perpetrator_first_name': results_case.perpetrator_first_name,
                'perpetrator_other_names': results_case.perpetrator_other_names,
                'perpetrator_surname': results_case.perpetrator_surname,
                'perpetrator_relationship': results_case.perpetrator_relationship_type,
                #'place_of_event': results_case.place_of_event,
                #'case_nature': results_case.case_nature,
                'risk_level': results_case.risk_level,
                'immediate_needs': results_imm,
                'future_needs': results_fut,
                #'refferal_to': referrals,
                'case_remarks': results_case.case_remarks,
                'refferal_present': results_case.referral_present,
                'date_of_summon': date_of_summon,
                'summon_issued': summon_issued

            })

            return render(request, 'forms/edit_case_record_sheet.html',
                          {
                              'form': form, 'pcnt': perp_cnt,
                              'init_data': init_data,
                              'vals': vals, 'perpetrators': perpetrators,
                              'resultsets': resultsets,
                              'resultsets2': resultsets2
                          })
    except Exception as e:
        msg = 'An error occured trying to Edit OVCCaseRecord - %s' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        redirect_url = reverse(forms_registry)
        return HttpResponseRedirect(redirect_url)

    params = {}
    params['transaction_type_id'] = 'UPDU'
    params['interface_id'] = 'INTW'
    params['form_id'] = id
    save_audit_trail(request, params, 'FTPC')

    # Init data
    formslog = FormsLog.objects.get(form_id=id)
    init_data = RegPerson.objects.get(pk=formslog.person_id)

    msg = 'Case Record Sheet (%s %s) Update Succesfull' % (
        init_data.first_name, init_data.surname)
    messages.add_message(request, messages.INFO, msg)
    # redirect_url = reverse(forms_registry)
    redirect_url = reverse(case_info, kwargs={'case_id': cid})
    return HttpResponseRedirect(redirect_url)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_case_record_sheet(request, id):
    try:
        """Get Initial Data"""
        # f = FormsLog.objects.get(form_id=id, is_void=False)
        ovccr = OVCCaseRecord.objects.get(case_id=id, is_void=False)
        person_id = int(ovccr.person_id)
        # init_data = RegPerson.objects.filter(pk=person_id)
        f = {'form_id': id}

        # Get Siblings
        init_data = RegPerson.objects.filter(pk=person_id)
        reg_personsiblings = []

        regpersonsiblings = RegPersonsSiblings.objects.filter(
            child_person_id=person_id)
        for regpersonsibling in regpersonsiblings:
            reg_personsiblings.append(regpersonsibling.sibling_person)
        init_data.siblingpersons = reg_personsiblings

        reg_caregivers = []
        caregivers = RegPersonsGuardians.objects.filter(
            child_person_id=person_id)
        for caregiver in caregivers:
            caregiver_details = caregiver.guardian_person
            setattr(caregiver_details, 'relation', caregiver.relationship)
            reg_caregivers.append(caregiver_details)
        init_data.caregivers = reg_caregivers

        check_fields = ['sex_id',
                        'family_status_id',
                        'household_economics',
                        'mental_condition_id',
                        'mental_subcondition_id',
                        'physical_condition_id',
                        'physical_subcondition_id',
                        'other_condition_id',
                        'other_subcondition_id',
                        'case_reporter_id',
                        'perpetrator_status_id',
                        'relationship_type_id',
                        'perpetrator_id', 'risk_level_id',
                        'referral_destination_id',
                        'intervention_id',
                        'case_category_id', 'core_item_id',
                        'yesno_id', 'relationship_type_id',
                        'case_reporter_relationship_to_child',
                        'long_term_support_id',
                        'immediate_need_id']

        vals = get_dict(field_name=check_fields)

        ovcd = OVCEconomicStatus.objects.get(case_id=id, is_void=False)
        ovcfam = OVCFamilyStatus.objects.filter(case_id=id, is_void=False)
        ovccr = OVCCaseRecord.objects.get(case_id=id, is_void=False)
        ovcgeo = OVCCaseGeo.objects.get(case_id=id, is_void=False)
        ovcfrnds = OVCFriends.objects.filter(case_id=id, is_void=False)
        ovchobs = OVCHobbies.objects.filter(case_id=id, is_void=False)
        ovcmed = OVCMedical.objects.get(case_id=id, is_void=False)
        ovcccats = OVCCaseCategory.objects.filter(case_id=id, is_void=False)
        ovcneeds = OVCNeeds.objects.filter(case_id=id, is_void=False)
        ovcrefa = OVCReferral.objects.filter(case_id=id, is_void=False)
        perpetrators = OvcCasePersons.objects.filter(
            case_id=id, person_type='PERP')

        # Retrieve Medical Subconditions
        medical_id = ovcmed.medical_id
        ovcphymeds = OVCMedicalSubconditions.objects.filter(
            medical_id=medical_id, medical_condition='Physical', is_void=False)
        ovcmentmeds = OVCMedicalSubconditions.objects.filter(
            medical_id=medical_id, medical_condition='Mental', is_void=False)
        ovcothermeds = OVCMedicalSubconditions.objects.filter(
            medical_id=medical_id, medical_condition='Other', is_void=False)

        # Get OVCCaseCategory
        case_grouping_ids = []
        jsonCategorysData = []
        jsonSubCategorysData = []
        str_jsonsubcategorydata = ''
        resultsets = []
        ovcccats = OVCCaseCategory.objects.filter(
            case_id=id, is_void=False)
        """ Get case_grouping_ids[] """
        for ovcccat in ovcccats:
            case_grouping_id = str(ovcccat.case_grouping_id)
            if not case_grouping_id in case_grouping_ids:
                case_grouping_ids.append(str(case_grouping_id))

        """ Get Case Categories """
        ovcccats2 = None
        for case_grouping_id in case_grouping_ids:
            ovcccats2 = OVCCaseCategory.objects.filter(
                case_grouping_id=case_grouping_id)

            for ovcccat in ovcccats2:
                # OVCCaseSubCategory
                ovccasesubcategorys = OVCCaseSubCategory.objects.filter(
                    case_grouping_id=case_grouping_id)
                for ovccasesubcategory in ovccasesubcategorys:
                    jsonSubCategorysData.append(
                        translate(str(ovccasesubcategory.sub_category_id)))
                str_jsonsubcategorydata = ','.join(jsonSubCategorysData)

                jsonCategorysData.append({'case_category': ovcccat.case_category,
                                          'case_subcategorys': str_jsonsubcategorydata,
                                          'date_of_event': (ovcccat.date_of_event).strftime('%d-%b-%Y'),
                                          'place_of_event': ovcccat.place_of_event,
                                          'case_nature': ovcccat.case_nature,
                                          'case_grouping_id': str(ovcccat.case_grouping_id)
                                          })
                jsonSubCategorysData = []

        """ Create resultsets """
        resultsets.append(jsonCategorysData)

        # Get OVCReferral
        jsonData2 = []
        resultsets2 = []
        referral_grouping_ids = []
        """ Get referral_grouping_ids[] """
        for reffs in ovcrefa:
            referral_grouping_id = str(reffs.referral_grouping_id)
            if not referral_grouping_id in referral_grouping_ids:
                referral_grouping_ids.append(str(referral_grouping_id))
        """ Get Referral Actors """
        ovcrefa2 = None
        for referral_grouping_id in referral_grouping_ids:
            ovcrefa2 = OVCReferral.objects.filter(
                referral_grouping_id=referral_grouping_id)
            for ra in ovcrefa2:
                jsonData2.append({'refferal_actor_type': translate(ra.refferal_actor_type),
                                  'refferal_actor_specify': ra.refferal_actor_specify,
                                  'refferal_to': translate(ra.refferal_to),
                                  'referral_grouping_id': str(ra.referral_grouping_id)
                                  })
        resultsets2.append(jsonData2)
        # User audit trail
        app_user = AppUser.objects.filter(pk=ovccr.created_by).first()

        return render(request,
                      'forms/view_case_record_sheet.html',
                      {'init_data': init_data,
                       'vals': vals, 'result': f,
                       'ovcd': ovcd,
                       'ovccr': ovccr,
                       'ovcgeo': ovcgeo,
                       'ovcfrnds': ovcfrnds,
                       'ovchobs': ovchobs,
                       'ovcmed': ovcmed,
                       'ovcphymeds': ovcphymeds,
                       'ovcmentmeds': ovcmentmeds,
                       'ovcothermeds': ovcothermeds,
                       'ovcneeds': ovcneeds,
                       'perpetrators': perpetrators,
                       'ovcfam': ovcfam,
                       'resultsets': resultsets,
                       'resultsets2': resultsets2,
                       'app_user': app_user
                       })
    except Exception as e:
        msg = 'An error occured trying to view OVCCaseRecord - %s' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
    redirect_url = reverse(forms_registry)
    return HttpResponseRedirect(redirect_url)

@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def check_case_record_sheet(request, id):
    cid = str(id).replace('-', '')
    return view_case_record_sheet(request, cid)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_case_record_sheet(request, id):
    now = timezone.now()
    try:
        # OVCCaseRecord
        ovccr = OVCCaseRecord.objects.get(case_id=id)
        ovccr.is_void = True
        ovccr.save(update_fields=['is_void'])

        # OVCCaseGeo
        ovcgeo = OVCCaseGeo.objects.get(case_id=id)
        ovcgeo.is_void = True
        ovcgeo.save(update_fields=['is_void'])

        # OVCEconomicStatus
        ovcd = OVCEconomicStatus.objects.get(case_id=id)
        ovcd.is_void = True
        ovcd.save(update_fields=['is_void'])

        # OVCHobbies
        ovchobs = OVCHobbies.objects.filter(case_id=id)
        for ovchob in ovchobs:
            ovchob.is_void = True
            ovchob.save(update_fields=['is_void'])

        # OVCFriends
        ovcfrnds = OVCFriends.objects.filter(case_id=id)
        for ovcfrnd in ovcfrnds:
            ovcfrnd.is_void = True
            ovcfrnd.save(update_fields=['is_void'])

        # OVCMedical
        ovcmed = OVCMedical.objects.get(case_id=id)
        ovcmed.is_void = True
        ovcmed.save(update_fields=['is_void'])

        # OVCMedicalSubconditions
        ovcmedsubconds = OVCMedicalSubconditions.objects.filter(
            medical_id=ovcmed.medical_id)
        for ovcmedsubcond in ovcmedsubconds:
            ovcmedsubcond.is_void = True
            ovcmedsubcond.save(update_fields=['is_void'])

        # OVCCaseCategory
        ovcccats = OVCCaseCategory.objects.filter(case_id=id)
        for ovccat in ovcccats:
            ovccat.is_void = True
            ovccat.save(update_fields=['is_void'])

        # OVCReferral
        ovcrs = OVCReferral.objects.filter(case_id=id)
        for ovcr in ovcrs:
            ovcr.is_void = True
            ovcr.save(update_fields=['is_void'])

        # OVCNeeds
        ovcneeds = OVCNeeds.objects.filter(case_id=id)
        for ovcneed in ovcneeds:
            ovcneed.is_void = True
            ovcneed.save(update_fields=['is_void'])

        # FormsLog
        f = FormsLog.objects.get(form_id=id)
        f.is_void = True
        f.save(update_fields=['is_void'])

    except Exception as e:
        msg = 'Form delete error (%s).' % str(e)
        messages.add_message(request, messages.INFO, msg)

    msg = 'Form delete succesfull (%s).' % id
    messages.add_message(request, messages.INFO, msg)
    redirect_url = reverse(forms_registry)
    return HttpResponseRedirect(redirect_url)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@is_allowed_groups(['RGM', 'RGU', 'DSU', 'STD'])
def new_case_record_sheet(request, id):

    # Get Time
    now = timezone.now()
    msg = ''
    cpims_id = int(id)

    # Get logged in user
    username = request.user.get_username()
    app_user = AppUser.objects.get(username=username)

    # Set up container[] for case_ids
    case_ids = []

    try:
        if request.method == 'POST':

            form = OVC_FT3hForm(data=request.POST)

            # User ID
            user_id = app_user.id
            # Perpetrators
            all_perps_json = request.POST.get('all_perps', None)
            all_perps = json.loads(all_perps_json) if all_perps_json else None

            # OVC_Reporting
            case_reporter = request.POST.get('case_reporter')
            court_name = request.POST.get(
                'court_name') if request.POST.get('court_name') else None
            court_number = request.POST.get(
                'court_number') if request.POST.get('court_number') else None
            police_station = request.POST.get(
                'police_station') if request.POST.get('police_station') else None
            ob_number = request.POST.get(
                'ob_number') if request.POST.get('ob_number') else None
            case_reporter_first_name = request.POST.get(
                'case_reporter_first_name') if request.POST.get('case_reporter_first_name') else None
            case_reporter_other_names = request.POST.get(
                'case_reporter_other_names') if request.POST.get('case_reporter_other_names') else None
            case_reporter_surname = request.POST.get(
                'case_reporter_surname') if request.POST.get('case_reporter_surname') else None
            case_reporter_contacts = request.POST.get(
                'case_reporter_contacts') if request.POST.get('case_reporter_contacts') else None

            date_case_opened = request.POST.get('date_case_opened')
            if date_case_opened:
                date_case_opened = convert_date(date_case_opened)

            # OVCCaseGeo
            report_subcounty = request.POST.get('report_subcounty')
            report_ward = request.POST.get('report_ward')
            report_village = request.POST.get('report_village')
            report_orgunit = request.POST.get('report_orgunit')
            occurence_county = request.POST.get('occurence_county')
            occurence_subcounty = request.POST.get('occurence_subcounty')
            occurence_ward = request.POST.get('occurence_ward')
            occurence_village = request.POST.get('occurence_village')

            # OVC_Details
            person = request.POST.get('person')
            household_economic_status = request.POST.get('household_economics')
            family_status = request.POST.getlist('family_status')
            hobbies = request.POST.get('hobbies')
            friends = request.POST.get('friends')

            # OVC_Medical_SubConditions
            mental_subconditions = request.POST.getlist('mental_subcondition')
            physical_subconditions = request.POST.getlist(
                'physical_subcondition')
            other_subconditions = request.POST.getlist('other_subcondition')

            # OVC_Medical
            mental_condition = request.POST.get('mental_condition')
            physical_condition = request.POST.get('physical_condition')
            other_condition = request.POST.get('other_condition')

            # OVC_CaseRecord
            serial_number = request.POST.get('serial_number')

            perpetrator_status = request.POST.get(
                'perpetrator_status') if request.POST.get('perpetrator_status') else None
            perpetrator_first_name = request.POST.get(
                'perpetrator_first_name') if request.POST.get('perpetrator_first_name') else None
            perpetrator_other_names = request.POST.get(
                'perpetrator_other_names') if request.POST.get('perpetrator_other_names') else None
            perpetrator_surname = request.POST.get(
                'perpetrator_surname') if request.POST.get('perpetrator_surname') else None
            perpetrator_relationship = request.POST.get(
                'perpetrator_relationship') if request.POST.get('perpetrator_relationship') else None
            # place_of_event = request.POST.get('place_of_event')
            # case_nature = request.POST.get('case_nature')
            risk_level = request.POST.get('risk_level')
            immediate_needs = request.POST.getlist('immediate_needs')
            future_needs = request.POST.getlist('future_needs')
            case_remarks = request.POST.get('case_remarks')
            refferal_to = request.POST.getlist('refferal_to')
            refferal_present = request.POST.get('refferal_present')
            summon_issued = request.POST.get('summon_issued')
            summon_status = False if summon_issued == 'AYES' else None
            date_of_summon = request.POST.get('date_of_summon')
            if date_of_summon:
                date_of_summon = convert_date(date_of_summon)
            else:
                date_of_summon = None

            # Added for CTiP and Locations handling
            occurence_country = request.POST.get('occurence_country')
            occurence_city = request.POST.get('occurence_city')
            occurence_location = request.POST.get('occurence_location')
            occurence_sublocation = request.POST.get('occurence_sublocation')

            # 1. Setup persons
            # 2. Setup clone Ids
            persons = []
            persons.append(person)
            clone_ids_list = request.POST.get('clone_ids_list')
            if clone_ids_list:
                clone_ids_list = clone_ids_list.split(',')
                persons.extend(set(clone_ids_list))

            for person in persons:
                # form_id = request.POST.get('case_id')

                """ validate serial number """
                pers_id = int(person)
                serial_number = validate_serialnumber(
                    pers_id, report_subcounty, serial_number)

                case_id = uuid.uuid1()

                # OVCCaseRecord
                ovccaserecord = OVCCaseRecord(
                    case_id=case_id,
                    case_serial=serial_number,
                    perpetrator_status=perpetrator_status,
                    perpetrator_first_name=perpetrator_first_name,
                    perpetrator_other_names=perpetrator_other_names,
                    perpetrator_surname=perpetrator_surname,
                    perpetrator_relationship_type=perpetrator_relationship,
                    case_reporter=case_reporter,
                    court_name=court_name,
                    court_number=court_number,
                    police_station=police_station,
                    ob_number=ob_number,
                    case_reporter_first_name=case_reporter_first_name,
                    case_reporter_other_names=case_reporter_other_names,
                    case_reporter_surname=case_reporter_surname,
                    case_reporter_contacts=case_reporter_contacts,
                    date_case_opened=date_case_opened,
                    # case_nature=case_nature,
                    risk_level=risk_level,
                    date_of_summon=date_of_summon,
                    summon_status=summon_status,
                    case_remarks=case_remarks,
                    referral_present=refferal_present,
                    # parent_case_id = parent_case_id,
                    timestamp_created=now,
                    created_by=int(app_user.id),
                    person=RegPerson.objects.get(pk=int(str(person)))).save()

                # OVCCaseCategory
                case_category_list = request.POST.get('case_category_list')
                if case_category_list:
                    case_category_data = json.loads(case_category_list)
                    for case_categorys in case_category_data:
                        case_category = case_categorys['case_category']
                        date_of_event = case_categorys['date_of_event']
                        place_of_event = case_categorys['place_of_event']
                        case_nature = case_categorys['case_nature']
                        case_grouping_id = new_guid_32()
                        if date_of_event:
                            date_of_event = convert_date(date_of_event)

                        ovccasecategory = OVCCaseCategory(
                            # case_category_id=new_guid_32(),
                            case_id=OVCCaseRecord.objects.get(pk=case_id),
                            case_grouping_id=case_grouping_id,
                            case_category=case_category.strip(),
                            date_of_event=date_of_event,
                            place_of_event=place_of_event.strip(),
                            case_nature=case_nature.strip(),
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))
                        )
                        ovccasecategory.save()
                        new_pk = ovccasecategory.pk

                        # OVCCaseSubCategory
                        case_subcategorys = case_categorys['case_subcategory']
                        case_subcategorys = case_subcategorys.split(',')

                        # for case_subcategory in case_subcategorys:
                        for i, case_subcat in enumerate(case_subcategorys):
                            OVCCaseSubCategory(
                                case_category=OVCCaseCategory.objects.get(
                                    pk=new_pk),
                                case_grouping_id=case_grouping_id,
                                sub_category_id=case_subcat.strip(),
                                timestamp_created=now,
                                person=RegPerson.objects.get(pk=int(person))
                            ).save()

                # OVCCaseGeo
                OVCCaseGeo(
                    case_id=OVCCaseRecord.objects.get(pk=case_id),
                    report_subcounty=SetupGeography.objects.get(
                        pk=int(report_subcounty)),
                    report_ward=report_ward,
                    report_village=report_village,
                    report_orgunit=RegOrgUnit.objects.get(
                        pk=int(report_orgunit)),
                    occurence_county=SetupGeography.objects.get(
                        pk=int(occurence_county)),
                    occurence_subcounty=SetupGeography.objects.get(
                        pk=int(occurence_subcounty)),
                    occurence_ward=occurence_ward,
                    occurence_village=occurence_village,
                    timestamp_created=now,
                    person=RegPerson.objects.get(pk=int(person))).save()

                # OVCReferral
                referralactors_list = request.POST.get('referralactors_list')
                if referralactors_list:
                    referralactors_data = json.loads(referralactors_list)
                    for referralactors in referralactors_data:
                        refferal_actor_type = referralactors[
                            'refferal_destination_type']
                        referral_actor_description = referralactors[
                            'refferal_destination_description']
                        refferal_to = referralactors['refferal_to']
                        referral_grouping_id = new_guid_32()
                        OVCReferral(
                            case_id=OVCCaseRecord.objects.get(pk=case_id),
                            refferal_actor_type=refferal_actor_type,
                            refferal_actor_specify=referral_actor_description,
                            refferal_to=refferal_to,
                            referral_grouping_id=referral_grouping_id,
                            case_category=None,
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()

                # OVCEconomicStatus
                OVCEconomicStatus(
                    case_id=OVCCaseRecord.objects.get(pk=case_id),
                    household_economic_status=household_economic_status,
                    timestamp_created=now,
                    person=RegPerson.objects.get(pk=int(person))).save()

                # OVCFamilyStatus
                for i, familystatus in enumerate(family_status):
                    familystatus = familystatus.split(',')
                    for familystatus_ in familystatus:
                        OVCFamilyStatus(
                            case_id=OVCCaseRecord.objects.get(pk=case_id),
                            family_status=familystatus_,
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()

                # OVCHobbies
                if hobbies:
                    hobbies = str(hobbies).split(",")
                    # print 'Hobbies --------- %s' %hobbies
                    for hobby in hobbies:
                        OVCHobbies(
                            case_id=OVCCaseRecord.objects.get(pk=case_id),
                            hobby=hobby.upper(),
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()

                # OVCFriends
                if friends:
                    friends = str(friends).split(",")
                    # print 'OVCFriends split(","): %s' %friends
                    for i, friend in enumerate(friends):
                        names = (friends[i]).split()
                        # print 'OVCFriends split(",")[names]: %s' %names
                        if(len(names) == 1):
                            ffname = names[0]
                            foname = 'XXXX'
                            fsname = 'XXXX'
                        if(len(names) == 2):
                            ffname = names[0]
                            foname = names[1]
                            fsname = 'XXXX'
                        if(len(names) == 3):
                            ffname = names[0]
                            foname = names[1]
                            fsname = names[2]
                        OVCFriends(
                            case_id=OVCCaseRecord.objects.get(pk=case_id),
                            friend_firstname=ffname.upper(),
                            friend_other_names=foname.upper(),
                            friend_surname=fsname.upper(),
                            timestamp_created=now,
                            person=RegPerson.objects.get(pk=int(person))).save()
                # Save Other perpetrators
                if all_perps:
                    for one_perp in all_perps:
                        pers_id = int(person)
                        relation = one_perp['relation']
                        if relation == 'CGOR':
                            relation = one_perp['other_relation']
                        OvcCasePersons(
                            person_first_name=one_perp['first_name'],
                            person_other_names=one_perp['other_name'],
                            person_surname=one_perp['surname'],
                            person_relation=relation,
                            case_id=case_id,
                            person_id=pers_id).save()

                # OVCMedical
                medical_id = new_guid_32()
                OVCMedical(
                    medical_id=medical_id,
                    case_id=OVCCaseRecord.objects.get(pk=case_id),
                    mental_condition=mental_condition,
                    physical_condition=physical_condition,
                    other_condition=other_condition,
                    timestamp_created=now,
                    person=RegPerson.objects.get(pk=int(person))).save()

                # OVCMedicalSubconditions
                med_conditions = []
                if not mental_condition == "MNRM":
                    for i, mental_subcondition in enumerate(mental_subconditions):
                        mental_subcondition = mental_subcondition.split(',')
                        for mcondition in mental_subcondition:
                            med_conditions.append(
                                {"medical_condition": "Mental",
                                 "medical_subcondition": mcondition})
                if not physical_condition == "PNRM":
                    for i, physical_subcondition in enumerate(physical_subconditions):
                        physical_subcondition = physical_subcondition.split(
                            ',')
                        for pcondition in physical_subcondition:
                            med_conditions.append(
                                {"medical_condition": "Physical",
                                 "medical_subcondition": pcondition})
                if not other_condition == "CHNM":
                    for i, other_subcondition in enumerate(other_subconditions):
                        other_subcondition = other_subcondition.split(',')
                        for ocondition in other_subcondition:
                            med_conditions.append(
                                {"medical_condition": "Other",
                                 "medical_subcondition": ocondition})

                for med_condition in med_conditions:
                    OVCMedicalSubconditions(
                        medicalsubcond_id=new_guid_32(),
                        medical_id=OVCMedical.objects.get(pk=medical_id),
                        medical_condition=med_condition['medical_condition'],
                        medical_subcondition=med_condition[
                            'medical_subcondition'],
                        timestamp_created=now,
                        person=RegPerson.objects.get(pk=int(person))).save()

                # OVCNeeds
                if immediate_needs:
                    for i, immediate_need in enumerate(immediate_needs):
                        immediate_need = immediate_need.split(',')
                        for immediateneed in immediate_need:
                            OVCNeeds(
                                case_id=OVCCaseRecord.objects.get(pk=case_id),
                                need_description=immediateneed.upper(),
                                need_type='IMMEDIATE',
                                timestamp_created=now,
                                person=RegPerson.objects.get(pk=int(person))
                            ).save()
                if future_needs:
                    for i, future_need in enumerate(future_needs):
                        future_need = future_need.split(',')
                        for futureneed in future_need:
                            OVCNeeds(
                                case_id=OVCCaseRecord.objects.get(pk=case_id),
                                need_description=futureneed.upper(),
                                need_type='FUTURE',
                                timestamp_created=now,
                                person=RegPerson.objects.get(pk=int(person))
                            ).save()
                # Other case geos for CTiP - Country and locations
                geo_params = {}
                geo_params['country'] = occurence_country
                geo_params['city'] = occurence_city
                geo_params['location'] = occurence_location
                geo_params['sub_location'] = occurence_sublocation
                save_case_other_geos(case_id, pers_id, geo_params)

                # FormsLog
                FormsLog(
                    form_id=str(case_id).replace('-', ''),
                    form_type_id='FTPC',
                    timestamp_created=now,
                    app_user=int(app_user.id),
                    person=RegPerson.objects.get(pk=int(person))).save()

                # Collect CaseIds Used ##
                case_ids.append(str(case_id))

            if summon_issued == 'AYES':
                # Save Summons in OVCCaseEventSummon ##
                ovccaseevents = OVCCaseEvents(
                    # case_event_id=case_event_id,
                    case_event_type_id='SUMMON',
                    date_of_event=date_of_summon,
                    case_event_details='case_event_details',
                    case_event_notes='First Summon',
                    case_event_outcome='case_event_outcome',
                    next_hearing_date=None,
                    case_id=OVCCaseRecord.objects.get(pk=case_ids[0]),
                    app_user=AppUser.objects.get(pk=int(app_user.id))
                )
                ovccaseevents.save()
                summon_fk = ovccaseevents.pk

                OVCCaseEventSummon(
                    honoured=False,
                    summon_date=date_of_summon,
                    summon_note='First Summon',
                    case_category_id=None,
                    case_event_id=OVCCaseEvents.objects.get(
                        pk=summon_fk),
                ).save()

            # Setup parent_case_id
            parent_case_id = case_ids[0]
            case_ids.pop(0)
            if case_ids:
                ovccaserecords = OVCCaseRecord.objects.filter(
                    case_id__in=case_ids)
                for ovccaserecord in ovccaserecords:
                    ovccaserecord.parent_case_id = parent_case_id
                    ovccaserecord.save(update_fields=['parent_case_id'])

        else:
            # Get Subcounty of app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            area_ids = RegPersonsGeo.objects.filter(
                person_id=user_id, is_void=False)

            # Generate UUIDs()
            case_id = new_guid_32()  # uuid_1
            case_category_id = new_guid_32()  # uuid_2

            # Get Siblings
            init_data = RegPerson.objects.filter(pk=id)

            reg_personsiblings = []
            for data in init_data:
                regpersonsiblings = RegPersonsSiblings.objects.filter(
                    child_person=data.id)
                if regpersonsiblings:
                    for regpersonsibling in regpersonsiblings:
                        reg_personsiblings.append(
                            regpersonsibling.sibling_person)
            init_data.siblingpersons = reg_personsiblings

            # add guradians for purposes of prefilling
            guardians = RegPersonsGuardians.objects.select_related().filter(
                child_person=id, is_void=False, date_delinked=None)
            siblings = RegPersonsSiblings.objects.select_related().filter(
                child_person_id=id, is_void=False,
                date_delinked=None).exclude(sibling_person_id=id)
            # Reverse relationship
            osiblings = RegPersonsSiblings.objects.select_related().filter(
                sibling_person_id=id, is_void=False,
                date_delinked=None)
            # .exclude(sibling_person_id=id)
            child_ids = [gd.child_person_id for gd in osiblings]
            oguardians = RegPersonsGuardians.objects.select_related().filter(
                child_person_id__in=child_ids, is_void=False,
                date_delinked=None)
            guardians_all = guardians | oguardians

            check_fields = ['sex_id']
            default_serial = 'CCO/COUNTY/SUB-COUNTY/INSTITUTION/CASELOAD/00001/2015'
            vals = get_dict(field_name=check_fields)
            form = OVC_FT3hForm({
                'case_id': case_id,
                'case_category_id': case_category_id,
                'user_id': user_id,
                'person': id,
                'case_serial': default_serial})
            return render(request, 'forms/new_case_record_sheet.html',
                          {'form': form, 'init_data': init_data,
                           'vals': vals, 'guardians': guardians_all})

    except Exception as e:
        msg = msg + 'Case record sheet save error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)

        # Delete Related on Exception e
        for case_id in case_ids:
            if OVCCaseRecord.objects.filter(case_id=case_id):
                OVCCaseRecord.objects.filter(
                    case_id=case_id).update(is_void=True)

                if FormsLog.objects.filter(form_id=case_id):
                    FormsLog.objects.filter(
                        form_id=case_id).update(is_void=True)

        return HttpResponseRedirect(reverse(case_record_sheet))

    # Init data
    init_data = RegPerson.objects.get(pk=id)

    msg = 'Case Record Sheet (%s %s) Save Succesfull' % (
        init_data.first_name, init_data.surname)
    messages.add_message(request, messages.INFO, msg)
    redirect_url = '%s?cpims_id=%s' % (reverse(forms_registry), cpims_id)
    return HttpResponseRedirect(redirect_url)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@is_allowed_groups(['RGM', 'RGU', 'DSU', 'STD'])
def residential_placement(request):
    if request.method == 'POST':
        resultsets = None
        resultset = None
        result = None
        try:
            form = OVCSearchForm(
                data=request.POST, initial={'person_type': 'TBVC'})
            check_fields = ['sex_id', 'cadre_type_id', 'person_type_id',
                            'relationship_type_id', 'identifier_type_id']
            vals = get_dict(field_name=check_fields)

            person_type = 'TBVC'
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')
            number_of_results = 1000
            type_of_person = [person_type] if person_type else []
            include_died = False

            resultsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)

            if resultsets:
                for result in resultsets:
                    # 1. Check If Already Placed
                    ovcplcmnts = OVCPlacement.objects.filter(
                        person=result.id, is_void=False)
                    setattr(result, 'placed', 'PLACED') if ovcplcmnts else setattr(
                        result, 'placed', None)
                    # Check if discharged 
                    if ovcplcmnts:
                        for ovcplcmnt in ovcplcmnts:
                            try:
                                transfers = OVCDischargeFollowUp.objects.get(
                                    placement_id=ovcplcmnt.placement_id, is_void=False)
                                transfer_id = int(transfers.discharge_destination)
                            except Exception as e:
                                transfer_id = 0

                            placement_id = (
                                str(ovcplcmnt.placement_id)).replace('-', '')
                            setattr(result, 'placement_id', placement_id)
                            setattr(result, 'transfer_id', transfer_id)
                            setattr(result, 'is_active', ovcplcmnt.is_active)
                            setattr(result, 'case_record', ovcplcmnt.case_record_id)
                            setattr(result, 'institution_id',
                                    int(ovcplcmnt.residential_institution_name))
                    else:
                        setattr(result, 'placement_id', None)

                    # 2. Check If Has Case RecordSheet
                    ovccaserecordsheet = OVCCaseRecord.objects.filter(
                        person=result.id, is_void=False)
                    cases = []
                    for cs in ovccaserecordsheet:
                        cases.append({'case_id': cs.case_id })
                    case_count = ovccaserecordsheet.count()
                    setattr(result, 'caserecordsheet', case_count)
                    setattr(result, 'cases', cases)

                    # 3. Check If Referred To CCI(RMCI) or Rescue Home SI(RMRH)
                    expected_referrals = ['RMCI', 'RMRH']
                    existing_referrals = []
                    ovcreferrals = OVCReferral.objects.filter(
                        person=result.id, is_void=False)
                    if ovcreferrals:
                        for ovcreferral in ovcreferrals:
                            existing_referrals.append(
                                str(ovcreferral.refferal_actor_specify))
                            # existing_referrals.append(str(ovcreferral.refferal_to))
                        if ('RMCI' in existing_referrals) or ('RMRH' in existing_referrals):
                            setattr(result, 'referred', 'REFERRED')
                        else:
                            setattr(result, 'referred', None)
                    else:
                        setattr(result, 'referred', None)

                    # Add child_geo to result <object>
                    ovc_persongeos = RegPersonsGeo.objects.filter(person=int(
                        result.id)).values_list('area_id', flat=True).order_by('area_id')
                    geo_locs = []
                    for ovc_persongeo in ovc_persongeos:
                        area_id = str(ovc_persongeo)
                        geo_locs.append(translate_geo(int(area_id)))

                    persongeos = ', '.join(geo_locs)

                    setattr(result, 'ovc_persongeos', persongeos)

                msg = 'Showing results for (%s)' % search_string
                messages.add_message(request, messages.INFO, msg)
                return render(request, 'forms/residential_placement.html',
                              {'form': form,
                               'resultsets': resultsets,
                               'vals': vals,
                               'person_type': person_type})
            else:
                msg = 'No results for (%s).Name does not exist in database.' % search_string
                messages.add_message(request, messages.ERROR, msg)
        except Exception as e:
            msg = 'Search error - %s' % (str(e))
            messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(residential_placement))
    else:
        form = OVCSearchForm()
        return render(request, 'forms/residential_placement.html',
                      {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def ovc_search(request):
    if request.method == 'POST':
        resultsets = None
        person_type = None

        try:
            form = OVCSearchForm(
                data=request.POST, initial={'person_type': 'TBVC'})
            check_fields = ['sex_id',
                            'person_type_id',
                            'identifier_type_id']
            vals = get_dict(field_name=check_fields)

            person_type = 'TBVC'
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')
            number_of_results = 1000
            type_of_person = [person_type] if person_type else []
            include_died = False

            resultsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)

            if resultsets:
                for result in resultsets:
                    case_count = OVCCaseRecord.objects.filter(
                        person=int(result.id), is_void=False).count()
                    # Add case_count to result <object>
                    setattr(result, 'case_count', case_count)

                msg = 'Showing results for (%s)' % search_string
                messages.add_message(request, messages.INFO, msg)
                return render(request, 'forms/forms_index.html',
                              {'form': form,
                               'resultsets': resultsets,
                               'vals': vals,
                               'person_type': person_type})
            else:
                msg = 'No results for (%s).Name does not exist in database.' % search_string
                messages.add_message(request, messages.ERROR, msg)
        except Exception as e:
            msg = 'OVC search error - %s' % (str(e))
            messages.add_message(request, messages.INFO, msg)
        return HttpResponseRedirect(reverse(ovc_search))
    else:
        form = OVCSearchForm(initial={'search_criteria': 'NAME'})
        return render(request, 'forms/forms_index.html',
                      {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@is_allowed_groups(['RGM', 'RGU', 'DSU', 'STD'])
def alternative_family_care(request):
    if request.method == 'POST':
        resultsets = None
        resultset = None
        result = None
        try:
            form = OVCSearchForm(
                data=request.POST, initial={'person_type': 'TBVC'})
            check_fields = ['sex_id']
            vals = get_dict(field_name=check_fields)

            person_type = 'TBVC'
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')
            number_of_results = 1000
            type_of_person = [person_type] if person_type else []
            include_died = False

            resultsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)

            if resultsets:
                for result in resultsets:
                    case_count = OVCCaseRecord.objects.filter(
                        person=int(result.id), is_void=False).count()
                    # Add case_count to result <object>
                    setattr(result, 'case_count', case_count)

                    # Add child_geo to result <object>
                    ovc_persongeos = RegPersonsGeo.objects.filter(person=int(
                        result.id)).values_list('area_id', flat=True).order_by('area_id')
                    geo_locs = []
                    for ovc_persongeo in ovc_persongeos:
                        area_id = str(ovc_persongeo)
                        geo_locs.append(translate_geo(int(area_id)))

                    persongeos = ', '.join(geo_locs)

                    setattr(result, 'ovc_persongeos', persongeos)

                msg = 'Showing results for (%s)' % search_string
                messages.add_message(request, messages.INFO, msg)
                return render(request, 'forms/alternative_family_care.html',
                              {'form': form,
                               'resultsets': resultsets,
                               'vals': vals,
                               'person_type': person_type})
            else:
                msg = 'No results for (%s).Name does not exist in database.' % search_string
                messages.add_message(request, messages.ERROR, msg)
        except Exception as e:
            msg = 'Search error - %s' % (str(e))
            messages.add_message(request, messages.INFO, msg)
        return HttpResponseRedirect(reverse(alternative_family_care))
    else:
        form = OVCSearchForm(initial={'search_criteria': 'NAME'})
        return render(request, 'forms/alternative_family_care.html',
                      {'form': form})


@login_required
#@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_alternative_family_care(request, id):
    # Get logged in user
    username = request.user.get_username()
    app_user = AppUser.objects.get(username=username)

    try:
        if request.method == 'POST':
            form = OVC_FTFCForm(data=request.POST)

            now = timezone.now()
            type_of_care = request.POST.get('type_of_care')
            residential_institution_name = request.POST.get(
                'residential_institution_name') if request.POST.get('residential_institution_name') else None
            fostered_from = request.POST.get(
                'fostered_from') if request.POST.get('fostered_from') else None
            certificate_number = request.POST.get(
                'certificate_number') if request.POST.get('certificate_number') else None
            date_of_certificate_expiry = request.POST.get(
                'date_of_certificate_expiry') if request.POST.get('date_of_certificate_expiry') else None
            if date_of_certificate_expiry:
                date_of_certificate_expiry = convert_date(
                    date_of_certificate_expiry)
            type_of_adoption = request.POST.get(
                'type_of_adoption') if request.POST.get('type_of_adoption') else None
            adoption_subcounty = request.POST.get(
                'adoption_subcounty') if request.POST.get('adoption_subcounty') else None
            adoption_country = request.POST.get(
                'adoption_country') if request.POST.get('adoption_country') else None
            court_name = request.POST.get(
                'court_name') if request.POST.get('court_name') else None
            court_file_number = request.POST.get(
                'court_file_number') if request.POST.get('court_file_number') else None
            date_of_adoption = request.POST.get('date_of_adoption')
            if date_of_adoption:
                date_of_adoption = convert_date(date_of_adoption)
            adopting_mother_firstname = request.POST.get(
                'adopting_mother_firstname') if request.POST.get('adopting_mother_firstname') else None
            adopting_mother_othernames = request.POST.get(
                'adopting_mother_othernames') if request.POST.get('adopting_mother_othernames') else None
            adopting_mother_surname = request.POST.get(
                'adopting_mother_surname') if request.POST.get('adopting_mother_surname') else None
            adopting_mother_idnumber = request.POST.get(
                'adopting_mother_idnumber') if request.POST.get('adopting_mother_idnumber') else None
            adopting_mother_contacts = request.POST.get(
                'adopting_mother_contacts') if request.POST.get('adopting_mother_contacts') else None
            adopting_father_firstname = request.POST.get(
                'adopting_father_firstname') if request.POST.get('adopting_father_firstname') else None
            adopting_father_othernames = request.POST.get(
                'adopting_father_othernames') if request.POST.get('adopting_father_othernames') else None
            adopting_father_surname = request.POST.get(
                'adopting_father_surname') if request.POST.get('adopting_father_surname') else None
            adopting_father_idnumber = request.POST.get(
                'adopting_father_idnumber') if request.POST.get('adopting_father_idnumber') else None
            adopting_father_contacts = request.POST.get(
                'adopting_father_contacts') if request.POST.get('adopting_father_contacts') else None
            adopting_agency = request.POST.get(
                'adopting_agency') if request.POST.get('adopting_agency') else None
            adoption_remarks = request.POST.get(
                'adoption_remarks') if request.POST.get('adoption_remarks') else None
            ##
            parental_status = request.POST.get(
                'parental_status') if request.POST.get('parental_status') else None
            contact_person = request.POST.get(
                'contact_person') if request.POST.get('contact_person') else None
            children_office = request.POST.get(
                'children_office') if request.POST.get('children_office') else None

            if adoption_subcounty:
                adoption_subcounty = SetupGeography.objects.get(
                    pk=int(adoption_subcounty))

            if fostered_from:
                fostered_from = RegOrgUnit.objects.get(
                    pk=int(fostered_from))

            if residential_institution_name:
                residential_institution_name = RegOrgUnit.objects.get(
                    pk=int(residential_institution_name))

            if children_office:
                children_office = RegOrgUnit.objects.get(
                    pk=int(children_office))

            # OVCFamilyCare
            ovc_familycare = OVCFamilyCare(
                type_of_care=type_of_care,
                certificate_number=certificate_number,
                date_of_certificate_expiry=date_of_certificate_expiry,
                type_of_adoption=type_of_adoption,
                adoption_subcounty=adoption_subcounty,
                adoption_country=adoption_country,
                court_name=court_name,
                court_file_number=court_file_number,
                date_of_adoption=date_of_adoption,
                adopting_mother_firstname=adopting_mother_firstname,
                adopting_mother_othernames=adopting_mother_othernames,
                adopting_mother_surname=adopting_mother_surname,
                adopting_mother_idnumber=adopting_mother_idnumber,
                adopting_mother_contacts=adopting_mother_contacts,
                adopting_father_firstname=adopting_father_firstname,
                adopting_father_othernames=adopting_father_othernames,
                adopting_father_surname=adopting_father_surname,
                adopting_father_idnumber=adopting_father_idnumber,
                adopting_father_contacts=adopting_father_contacts,
                adopting_agency=adopting_agency,
                adoption_remarks=adoption_remarks,
                ##
                residential_institution_name=residential_institution_name,
                fostered_from=fostered_from,
                parental_status=parental_status,
                contact_person=contact_person,
                children_office=children_office,
                person=RegPerson.objects.get(pk=int(id)),
                created_by=int(app_user.id),
                timestamp_created=now
            )
            ovc_familycare.save()
            familycare_pk = ovc_familycare.pk

            # FormsLog
            FormsLog(
                form_id=str(familycare_pk).replace('-', ''),
                form_type_id='FTFC',
                timestamp_created=now,
                person=RegPerson.objects.get(pk=int(id))).save()

            # Init data
            init_data = RegPerson.objects.get(pk=id)

            msg = 'Alternative Family Care (%s %s) Save Succesfull' % (
                init_data.first_name, init_data.surname)
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseRedirect(reverse(alternative_family_care))
        else:
            print('Not a POST')
            """
            # Init data
            check_fields = ['sex_id']
            vals = get_dict(field_name=check_fields)
            init_data = RegPerson.objects.filter(pk=id)
            form = OVC_FTFCForm()
            return render(request,
                          'forms/new_alternative_family_care.html',
                          {'form': form,
                           'init_data': init_data,
                           'vals': vals,
                           'person_id': id})
            """
    except Exception as e:
        msg = 'Alternative Family Care Save Error - %s' % str(e)
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(alternative_family_care))
    # Init data
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    init_data = RegPerson.objects.filter(pk=id)
    form = OVC_FTFCForm()
    return render(request,
                  'forms/new_alternative_family_care.html',
                  {'form': form,
                   'init_data': init_data,
                   'vals': vals,
                   'person_id': id})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_alternative_family_care(request, id):
    try:
        if request.method == 'POST':
            form = OVC_FTFCForm(data=request.POST)

            now = timezone.now()
            type_of_care = request.POST.get('type_of_care')
            residential_institution_name = request.POST.get(
                'residential_institution_name') if request.POST.get('residential_institution_name') else None
            fostered_from = request.POST.get(
                'fostered_from') if request.POST.get('fostered_from') else None
            certificate_number = request.POST.get(
                'certificate_number') if request.POST.get('certificate_number') else None
            date_of_certificate_expiry = request.POST.get(
                'date_of_certificate_expiry') if request.POST.get('date_of_certificate_expiry') else None
            if date_of_certificate_expiry:
                date_of_certificate_expiry = convert_date(
                    date_of_certificate_expiry)
            type_of_adoption = request.POST.get(
                'type_of_adoption') if request.POST.get('type_of_adoption') else None
            adoption_subcounty = request.POST.get(
                'adoption_subcounty') if request.POST.get('adoption_subcounty') else None
            adoption_country = request.POST.get(
                'adoption_country') if request.POST.get('adoption_country') else None
            court_name = request.POST.get(
                'court_name') if request.POST.get('court_name') else None
            court_file_number = request.POST.get(
                'court_file_number') if request.POST.get('court_file_number') else None
            date_of_adoption = request.POST.get('date_of_adoption')
            if date_of_adoption:
                date_of_adoption = convert_date(date_of_adoption)
            adopting_mother_firstname = request.POST.get(
                'adopting_mother_firstname') if request.POST.get('adopting_mother_firstname') else None
            adopting_mother_othernames = request.POST.get(
                'adopting_mother_othernames') if request.POST.get('adopting_mother_othernames') else None
            adopting_mother_surname = request.POST.get(
                'adopting_mother_surname') if request.POST.get('adopting_mother_surname') else None
            adopting_mother_idnumber = request.POST.get(
                'adopting_mother_idnumber') if request.POST.get('adopting_mother_idnumber') else None
            adopting_mother_contacts = request.POST.get(
                'adopting_mother_contacts') if request.POST.get('adopting_mother_contacts') else None
            adopting_father_firstname = request.POST.get(
                'adopting_father_firstname') if request.POST.get('adopting_father_firstname') else None
            adopting_father_othernames = request.POST.get(
                'adopting_father_othernames') if request.POST.get('adopting_father_othernames') else None
            adopting_father_surname = request.POST.get(
                'adopting_father_surname') if request.POST.get('adopting_father_surname') else None
            adopting_father_idnumber = request.POST.get(
                'adopting_father_idnumber') if request.POST.get('adopting_father_idnumber') else None
            adopting_father_contacts = request.POST.get(
                'adopting_father_contacts') if request.POST.get('adopting_father_contacts') else None
            adopting_agency = request.POST.get(
                'adopting_agency') if request.POST.get('adopting_agency') else None
            adoption_remarks = request.POST.get(
                'adoption_remarks') if request.POST.get('adoption_remarks') else None
            ##
            parental_status = request.POST.get(
                'parental_status') if request.POST.get('parental_status') else None
            contact_person = request.POST.get(
                'contact_person') if request.POST.get('contact_person') else None
            children_office = request.POST.get(
                'children_office') if request.POST.get('children_office') else None

            if adoption_subcounty:
                adoption_subcounty = SetupGeography.objects.get(
                    pk=int(adoption_subcounty))

            if fostered_from:
                fostered_from = RegOrgUnit.objects.get(
                    pk=int(fostered_from))

            if residential_institution_name:
                residential_institution_name = RegOrgUnit.objects.get(
                    pk=int(residential_institution_name))

            if children_office:
                children_office = RegOrgUnit.objects.get(
                    pk=int(children_office))

            # OVCFamilyCare
            ovc_familycare = OVCFamilyCare.objects.get(
                familycare_id=id, is_void=False)
            ovc_familycare.type_of_care = type_of_care
            ovc_familycare.certificate_number = certificate_number
            ovc_familycare.date_of_certificate_expiry = date_of_certificate_expiry
            ovc_familycare.type_of_adoption = type_of_adoption
            ovc_familycare.adoption_subcounty = adoption_subcounty
            ovc_familycare.adoption_country = adoption_country
            ovc_familycare.court_name = court_name
            ovc_familycare.court_file_number = court_file_number
            ovc_familycare.date_of_adoption = date_of_adoption
            ovc_familycare.adopting_mother_firstname = adopting_mother_firstname
            ovc_familycare.adopting_mother_othernames = adopting_mother_othernames
            ovc_familycare.adopting_mother_surname = adopting_mother_surname
            ovc_familycare.adopting_mother_idnumber = adopting_mother_idnumber
            ovc_familycare.adopting_mother_contacts = adopting_mother_contacts
            ovc_familycare.adopting_father_firstname = adopting_father_firstname
            ovc_familycare.adopting_father_othernames = adopting_father_othernames
            ovc_familycare.adopting_father_surname = adopting_father_surname
            ovc_familycare.adopting_father_idnumber = adopting_father_idnumber
            ovc_familycare.adopting_father_contacts = adopting_father_contacts
            ovc_familycare.adopting_agency = adopting_agency
            ovc_familycare.adoption_remarks = adoption_remarks
            ##
            ovc_familycare.residential_institution_name = residential_institution_name
            ovc_familycare.fostered_from = fostered_from
            ovc_familycare.parental_status = parental_status
            ovc_familycare.contact_person = contact_person
            ovc_familycare.children_office = children_office
            ovc_familycare.save(update_fields=['residential_institution_name', 'fostered_from', 'parental_status',
                                               'contact_person', 'children_office', 'type_of_care', 'certificate_number', 'date_of_certificate_expiry',
                                               'type_of_adoption', 'adoption_subcounty', 'adoption_country', 'court_name', 'court_file_number',
                                               'date_of_adoption', 'adopting_mother_firstname', 'adopting_mother_othernames', 'adopting_mother_surname',
                                               'adopting_mother_idnumber', 'adopting_mother_contacts', 'adopting_father_firstname', 'adopting_father_othernames',
                                               'adopting_father_surname', 'adopting_father_idnumber', 'adopting_father_contacts', 'adopting_agency', 'adoption_remarks'])

            # FormsLog
            f = FormsLog.objects.get(form_id=id)
            f.timestamp_modified = now
            f.save(update_fields=['timestamp_modified'])

            params = {}
            params['transaction_type_id'] = 'UPDU'
            params['interface_id'] = 'INTW'
            params['form_id'] = id
            save_audit_trail(request, params, 'FTFC')

            # Init data
            init_data = RegPerson.objects.filter(pk=f.person_id)
            first_name = ''
            surname = ''
            for data in init_data:
                first_name = data.first_name
                surname = data.surname

            msg = 'Alternative Family Care (%s %s) Update Succesfull' % (
                first_name, surname)
            messages.add_message(request, messages.INFO, msg)
            redirect_url = reverse(forms_registry)
            return HttpResponseRedirect(redirect_url)

        else:
            # OVCFamilyCare
            ovc_familycare_results = OVCFamilyCare.objects.get(
                familycare_id=id, is_void=False)

            # Basic Data
            init_data = RegPerson.objects.filter(
                pk=int(ovc_familycare_results.person_id))

            # Convert Dates
            date_of_adoption = ovc_familycare_results.date_of_adoption
            if date_of_adoption:
                date_of_adoption = date_of_adoption.strftime('%d-%b-%Y')

            date_of_certificate_expiry = ovc_familycare_results.date_of_certificate_expiry
            if date_of_certificate_expiry:
                date_of_certificate_expiry = date_of_certificate_expiry.strftime(
                    '%d-%b-%Y')

            form = OVC_FTFCForm({
                'type_of_care': ovc_familycare_results.type_of_care,
                'certificate_number': ovc_familycare_results.certificate_number,
                'date_of_certificate_expiry': date_of_certificate_expiry,
                'type_of_adoption': ovc_familycare_results.type_of_adoption,
                'date_of_adoption': date_of_adoption,
                'adopting_mother_firstname': ovc_familycare_results.adopting_mother_firstname,
                'adopting_mother_othernames': ovc_familycare_results.adopting_mother_othernames,
                'adopting_mother_surname': ovc_familycare_results.adopting_mother_surname,
                'adopting_mother_idnumber': ovc_familycare_results.adopting_mother_idnumber,
                'adopting_mother_contacts': ovc_familycare_results.adopting_mother_contacts,
                'adopting_father_firstname': ovc_familycare_results.adopting_father_firstname,
                'adopting_father_othernames': ovc_familycare_results.adopting_father_othernames,
                'adopting_father_surname': ovc_familycare_results.adopting_father_surname,
                'adopting_father_idnumber': ovc_familycare_results.adopting_father_idnumber,
                'adopting_father_contacts': ovc_familycare_results.adopting_father_contacts,
                'adopting_agency': ovc_familycare_results.adopting_agency,
                'adoption_remarks': ovc_familycare_results.adoption_remarks,
                'adoption_country': ovc_familycare_results.adoption_country,
                'adoption_subcounty': ovc_familycare_results.adoption_subcounty.area_id if ovc_familycare_results.adoption_subcounty else '',
                'court_name': ovc_familycare_results.court_name,
                'court_file_number': ovc_familycare_results.court_file_number,
                'parental_status': ovc_familycare_results.parental_status,
                'children_office': ovc_familycare_results.children_office,
                'contact_person': ovc_familycare_results.contact_person,
                'residential_institution_name': ovc_familycare_results.residential_institution_name,
                'fostered_from': ovc_familycare_results.fostered_from
            })

            check_fields = ['sex_id']
            vals = get_dict(field_name=check_fields)
            return render(request, 'forms/edit_alternative_family_care.html',
                          {'form': form,
                           'init_data': init_data,
                           'vals': vals,
                           'adoption_country': ovc_familycare_results.adoption_country})
    except Exception as e:
        msg = 'Alternative Family Care Edit Error - %s' % str(e)
        messages.add_message(request, messages.ERROR, msg)
        redirect_url = reverse(forms_registry)
        return HttpResponseRedirect(redirect_url)

    form = OVC_FTFCForm()
    return render(request,
                  'forms/edit_alternative_family_care.html')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_alternative_family_care(request, id):
    try:
        ovc_familycare_results = OVCFamilyCare.objects.get(
            familycare_id=id, is_void=False)

        # Init data
        init_data = RegPerson.objects.filter(
            pk=ovc_familycare_results.person_id)
        check_fields = [
            'sex_id',
            'adoption_id',
            'parental_status_id',
            'alternative_family_care_type_id']
        print('ovc_familycare_results ---------  %s' % ovc_familycare_results)
        vals = get_dict(field_name=check_fields)
        return render(request,
                      'forms/view_alternative_family_care.html',
                      {'ovc_familycare_results': ovc_familycare_results,
                       'vals': vals,
                       'init_data': init_data})
    except Exception as e:
        msg = 'Alternative Family Care View Error - %s' % str(e)
        messages.add_message(request, messages.ERROR, msg)
        redirect_url = reverse(forms_registry)
        return HttpResponseRedirect(redirect_url)
    return render(request,
                  'forms/view_alternative_family_care.html')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def case_events(request, id):
    check_fields = ['intervention_id',
                    'case_nature_id',
                    'risk_level_id',
                    'case_category_id',
                    'core_item_id',
                    'event_place_id',
                    'sex_id',
                    'referral_type_id']
    vals = get_dict(field_name=check_fields)

    resultsets = set()

    # FormsLog
    init_data = None
    forms = FormsLog.objects.filter(form_id=id, is_void=False)
    for f in forms:
        person_id = int(f.person_id)
        init_data = RegPerson.objects.filter(pk=person_id)

    resultsets.add(forms)

    # OVCCaseEvents
    c_events = OVCCaseEvents.objects.filter(
        case_id=id, is_void=False).order_by('-timestamp_created')

    # OVCCaseRecord
    ovccr = OVCCaseRecord.objects.filter(case_id=id, is_void=False)

    # OVCCaseCategory
    ovcccats = OVCCaseCategory.objects.filter(case_id=id, is_void=False)

    # Get case_grouping_ids[]
    case_grouping_ids = []
    for ovcccat in ovcccats:
        case_grouping_id = str(ovcccat.case_grouping_id)
        if case_grouping_id not in case_grouping_ids:
            case_grouping_ids.append(str(case_grouping_id))

    # OVCReferral
    ovcrefs = OVCReferral.objects.filter(case_id=id, is_void=False)

    # OVCCaseEvents
    ovcservices = []
    ovcclosures = []
    summon_count = 0
    afc_intvs = ['IADP', 'IFRC', 'GRDN', 'IKIN', 'IKAF', 'ISIL', 'ISCH']
    afc_intv = []
    for c_event in c_events:
        # 1. Services/Encounters
        ovcservices = OVCCaseEventServices.objects.filter(
            case_event_id=c_event.case_event_id,
            is_void=False).order_by('-timestamp_created')
        for intv in ovcservices:
            if intv.service_provided in afc_intvs:
                afc_intv.append(intv.service_provided)

        # 2. Closures
        ovcclosures = OVCCaseEventClosure.objects.filter(
            case_event_id=c_event.case_event_id,
            is_void=False).order_by('-timestamp_created')

        # 3. Summon Count
        summon_count += OVCCaseEventSummon.objects.filter(
            case_event_id=c_event.case_event_id, is_void=False).count()

    # Generate Resultsets Object
    for resultset in resultsets:
        for res in resultset:
            res.c_record = ovccr if ovccr else None
            res.c_evnts = ovcservices if ovcservices else None
            res.c_cats = ovcccats if ovcccats else None
            res.c_refs = ovcrefs if ovcrefs else None
            res.c_close = ovcclosures if ovcclosures else None
            # res.c_record =(res.c_record).(res.c_close)

    # Check if there are AFC Related closures
    print('prepare for AFC', afc_intv)

    case_id = ''
    date_case_opened = ''
    for ovccrecord in ovccr:
        case_id = ovccrecord.case_id
        date_case_opened = ovccrecord.date_case_opened

    form = OVC_CaseEventForm(
        initial={'case_id': case_id,
                 'reported_date': date_case_opened.strftime('%d-%b-%Y')})
    crs = ovccr.first()
    return render(request, 'forms/case_events.html',
                  {
                      'form': form, 'vals': vals,
                      'resultsets': resultsets, 'afc': afc_intv,
                      'init_data': init_data, 'case_id': case_id,
                      'summon_count': summon_count, 'crs': crs
                  })


def save_encounter(request):
    now = timezone.now()
    case_event_id = uuid.uuid4()
    user_id = 0

    try:
        if request.method == 'POST':

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            cid = request.POST.get('case_id')
            encounter_notes = request.POST.get('encounter_notes')
            case_category_id = request.POST.get('case_category_id')
            service_provided_list = request.POST.get('service_provided_list')
            date_of_encounter_event = now

            case_id = uuid.UUID(str(cid))

            # OVCCaseEvents
            ovccaseevents = OVCCaseEvents(
                case_event_id=case_event_id,
                case_event_type_id='SERVICES',
                date_of_event=date_of_encounter_event,
                case_event_details='case_event_details',
                case_event_notes=encounter_notes,
                case_id=OVCCaseRecord.objects.get(pk=case_id),
                app_user=AppUser.objects.get(pk=user_id)
            ).save()

            # OVCCaseEventServices
            if service_provided_list:
                service_provided_data = json.loads(service_provided_list)
                for svc_provided in service_provided_data:
                    service_grouping_id = uuid.uuid4()
                    service_provided = svc_provided['service_provided']
                    service_provider = svc_provided['service_provider']
                    place_of_service = svc_provided['place_of_service']
                    date_of_encounter_event = svc_provided[
                        'date_of_encounter_event']
                    if date_of_encounter_event:
                        date_of_encounter_event = convert_date(
                            date_of_encounter_event)
                    OVCCaseEventServices(
                        # service_id = new_guid_32(),
                        service_provided=service_provided,
                        service_provider=service_provider,
                        place_of_service=place_of_service,
                        date_of_encounter_event=date_of_encounter_event,
                        service_grouping_id=service_grouping_id,
                        case_event_id=OVCCaseEvents.objects.get(
                            pk=case_event_id),
                        case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()

            # Update Summon Status
            ovcr = OVCCaseRecord.objects.get(pk=case_id)
            ovcr.summon_status = True
            ovcr.case_stage = 1
            ovcr.save(update_fields=['summon_status', 'case_stage'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error saving Encounters/Services - %s ' % str(e))
    return HttpResponse('Encounter Saved')


def view_encounter(request):
    resultsets = []
    ovc_events = None
    ovc_services = []
    ovc_category_ids = []
    jsonCeData = []
    jsonSvcsData = []
    service_grouping_ids = []

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')
            ovc_events_svcs = OVCCaseEventServices.objects.filter(
                case_event_id=case_event_id, is_void=False)

            """ Get service_grouping_ids[] """
            for ovc_events_svc in ovc_events_svcs:
                ovc_category_ids.append(
                    str(ovc_events_svc.case_category_id))
                service_grouping_id = str(ovc_events_svc.service_grouping_id)
                if not service_grouping_id in service_grouping_ids:
                    service_grouping_ids.append(str(service_grouping_id))

            """ Get Services Provided """
            # print 'ovc_category_ids ------- %s' %ovc_category_ids
            ovc_events_svcs2 = None
            for service_grouping_id in service_grouping_ids:
                ovc_events_svcs2 = OVCCaseEventServices.objects.filter(
                    service_grouping_id=service_grouping_id)
                for ovc_events_svc2 in ovc_events_svcs2:
                    jsonSvcsData.append({
                        'pk': str(ovc_events_svc2.service_id),
                        'service_provided': translate(ovc_events_svc2.service_provided),
                        'service_provided_id': ovc_events_svc2.service_provided,
                        'service_provider': translate(ovc_events_svc2.service_provider),
                        'service_provider_id': ovc_events_svc2.service_provider,
                        'place_of_service': str(ovc_events_svc2.place_of_service),
                        'date_of_encounter_event': str(ovc_events_svc2.date_of_encounter_event),
                        'service_grouping_id': str(ovc_events_svc2.service_grouping_id)
                    })

            """ Create resultsets """
            resultsets.append(jsonSvcsData)

            ovc_events = OVCCaseEvents.objects.filter(
                case_event_id=case_event_id, is_void=False)
            for ovc_event in ovc_events:
                # print 'ovc_event.case_event_id -- %s'
                # %ovc_event.case_event_id
                jsonCeData.append({'case_event_id': str(ovc_event.case_event_id),
                                   'case_event_type_id': str(ovc_event.case_event_type_id),
                                   'date_of_event': str(ovc_event.date_of_event),
                                   'case_event_notes': str(ovc_event.case_event_notes),
                                   'case_category': ovc_category_ids[0],
                                   'resultsets': resultsets
                                   })
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error viewing Encounters/Services - %s ' % str(e))
    return JsonResponse(jsonCeData, content_type='application/json',
                        safe=False)


def edit_encounter(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            case_id = request.POST.get('case_id')
            case_event_id = request.POST.get('case_event_id')
            encounter_notes = request.POST.get('encounter_notes')
            case_category_id = request.POST.get('case_category_id')
            service_provided_list = request.POST.get('service_provided_list')
            date_of_encounter_event = now

            # Update OVCCaseEvents
            ovc_ce = OVCCaseEvents.objects.get(pk=case_event_id)
            ovc_ce.case_event_notes = encounter_notes
            ovc_ce.save(update_fields=['date_of_event', 'case_event_notes'])

            # Update OVCCaseEventServices
            existing_services = []
            new_services = []
            existing_services = OVCCaseEventServices.objects.filter(
                case_event_id=case_event_id).values_list('service_provided', flat=True)

            if service_provided_list:
                service_provided_data = json.loads(service_provided_list)
                for svc_provided in service_provided_data:
                    service_grouping_id = new_guid_32(),
                    service_provided = svc_provided['service_provided']
                    service_provider = svc_provided['service_provider']
                    place_of_service = svc_provided['place_of_service']
                    service_status = svc_provided['service_status']
                    date_of_encounter_event = svc_provided[
                        'date_of_encounter_event']
                    if date_of_encounter_event:
                        date_of_encounter_event = convert_date(
                            date_of_encounter_event)

                    if service_status == 'new':
                        OVCCaseEventServices(
                            # service_id = new_guid_32(),
                            service_provided=service_provided,
                            service_provider=service_provider,
                            place_of_service=place_of_service,
                            date_of_encounter_event=date_of_encounter_event,
                            service_grouping_id=service_grouping_id,
                            case_event_id=OVCCaseEvents.objects.get(
                                pk=case_event_id),
                            case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()

            # Update Case Category Id Provided
            ovc_services = OVCCaseEventServices.objects.filter(
                case_event_id=case_event_id)
            for ovc_service in ovc_services:
                ovc_service.case_category = case_category_id
                ovc_service.save(
                    update_fields=['case_category'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error updating Encounters/Services - %s ' % str(e))
    return HttpResponse('Encounter Updated')


def delete_encounter(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('case_event_id')
            service_id = request.POST.get('service_id')

            'service_id ----- %s' % service_id

            # Handling emove functionality
            if service_id:
                ovccaseeventservices = OVCCaseEventServices.objects.filter(
                    case_event_id=case_event_id).count()
                print('ovccaseeventservices --- %s' % ovccaseeventservices)
                if ovccaseeventservices > 1:
                    OVCCaseEventServices.objects.filter(
                        service_id=service_id).update(is_void=True)
                else:
                    return HttpResponse('Error deleting Encounters/Services')
            else:
                # Update OVCCaseEvents
                ovc_ce = OVCCaseEvents.objects.get(pk=case_event_id)
                ovc_ce.is_void = True
                ovc_ce.save(update_fields=['is_void'])

                # Delete/Void Services Provided
                ovc_services = OVCCaseEventServices.objects.filter(
                    case_event_id=case_event_id)
                for ovc_service in ovc_services:
                    ovc_service.is_void = True
                    ovc_service.save(update_fields=['is_void'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error deleting Encounters/Services - %s ' % str(e))
    # return HttpResponseRedirect(reverse(ovc_search))
    return HttpResponse('Encounter Deleted')


def save_court(request):
    try:
        if request.method == 'POST':
            case_event_id = new_guid_32()

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            case_category_id = request.POST.get('court_session_case')
            court_session_type = request.POST.get('court_session_type')
            date_of_court_event = request.POST.get('date_of_court_event')
            if date_of_court_event:
                date_of_court_event = convert_date(date_of_court_event)
            court_notes = request.POST.get('court_notes')
            next_hearing_date = request.POST.get('next_hearing_date')
            if next_hearing_date:
                next_hearing_date = convert_date(next_hearing_date)
            court_session_type = request.POST.get('court_session_type')
            next_mention_date = request.POST.get('next_mention_date')
            if next_mention_date:
                next_mention_date = convert_date(next_mention_date)
            plea_taken = request.POST.get(
                'plea_taken') if request.POST.get('plea_taken') else None
            application_outcome = request.POST.get(
                'application_outcome') if request.POST.get('application_outcome') else None
            court_outcome = request.POST.get('court_outcome')
            court_orders = request.POST.getlist('court_order')

            case_id = None
            casecategory = OVCCaseCategory.objects.get(pk=case_category_id)
            if casecategory:
                case_id = OVCCaseRecord.objects.get(
                    pk=casecategory.case_id_id)

            court_session_type = 'COURT MENTION' if court_session_type == 'STMN' else 'COURT HEARING'

            OVCCaseEvents(
                case_event_id=case_event_id,
                case_event_type_id=court_session_type,
                date_of_event=date_of_court_event,
                case_event_details='case_event_details',
                case_event_notes=court_notes,
                case_event_outcome=court_outcome,
                next_hearing_date=next_hearing_date,
                next_mention_date=next_mention_date,
                plea_taken=plea_taken,
                application_outcome=application_outcome,
                case_id=case_id,
                app_user=AppUser.objects.get(pk=user_id)
            ).save()

            if court_orders:
                for i, court_order in enumerate(court_orders):
                    court_order = court_order.split(',')
                    for order in court_order:
                        OVCCaseEventCourt(
                            court_order=order,
                            case_event_id=OVCCaseEvents.objects.get(
                                pk=case_event_id),
                            case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()
            else:
                OVCCaseEventCourt(
                    court_order=None,
                    case_event_id=OVCCaseEvents.objects.get(
                        pk=case_event_id),
                    case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error saving Court Sessions - %s ' % str(e))
    return HttpResponse('Court Session Saved')


def view_court(request):
    ovc_court_orders = []
    jsonCourtData = []
    ovc_category_ids = []
    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')

            ovc_court_events = OVCCaseEventCourt.objects.filter(
                case_event_id=case_event_id, is_void=False)
            for ovc_court_event in ovc_court_events:
                ovc_court_orders.append(str(ovc_court_event.court_order))
                ovc_category_ids.append(
                    str(ovc_court_event.case_category_id))

            ovc_events = OVCCaseEvents.objects.filter(
                case_event_id=case_event_id, is_void=False)
            for ovc_event in ovc_events:
                case_event_type_id = ovc_event.case_event_type_id

                # decode court_session_types
                if case_event_type_id == 'COURT MENTION':
                    case_event_type_id = 'STMN'
                if case_event_type_id == 'COURT HEARING':
                    case_event_type_id = 'STHR'
                if case_event_type_id == 'COURT PLEA':
                    case_event_type_id = 'STPL'
                if case_event_type_id == 'COURT APPLICATION':
                    case_event_type_id = 'STAP'

                 # Convert Dates
                date_of_event = ovc_event.date_of_event
                if date_of_event:
                    date_of_event = date_of_event.strftime('%d-%b-%Y')

                next_hearing_date = ovc_event.next_hearing_date
                if next_hearing_date:
                    next_hearing_date = next_hearing_date.strftime('%d-%b-%Y')

                next_mention_date = ovc_event.next_mention_date
                if next_mention_date:
                    next_mention_date = next_mention_date.strftime('%d-%b-%Y')

                jsonCourtData.append({'case_event_type_id': ovc_event.case_event_type_id,
                                      'case_event_id': str(ovc_event.case_event_id),
                                      'court_session_type': case_event_type_id,
                                      'date_of_event': date_of_event,
                                      'case_event_notes': str(ovc_event.case_event_notes),
                                      'court_outcome': str(ovc_event.case_event_outcome),
                                      'next_hearing_date': next_hearing_date,
                                      'next_mention_date': next_mention_date,
                                      'plea_taken': ovc_event.plea_taken,
                                      'application_outcome': ovc_event.application_outcome,
                                      'date_of_event': str(ovc_event.date_of_event),
                                      'ovc_court_orders': ovc_court_orders,
                                      'ovc_category_ids': ovc_category_ids[0]
                                      })

                print('jsonCourtData - %s' % jsonCourtData)
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error viewing Court Sessions - %s ' % str(e))
    return JsonResponse(jsonCourtData, content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_court(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            case_id = request.POST.get('case_id')
            case_event_id = request.POST.get('case_event_id')

            case_category_id = request.POST.get('court_session_case')
            court_session_type = request.POST.get('court_session_type')
            date_of_court_event = request.POST.get('date_of_court_event')
            if date_of_court_event:
                date_of_court_event = convert_date(date_of_court_event)
            court_notes = request.POST.get('court_notes')
            next_hearing_date = request.POST.get('next_hearing_date')
            if next_hearing_date:
                next_hearing_date = convert_date(next_hearing_date)
            court_session_type = request.POST.get('court_session_type')
            next_mention_date = request.POST.get('next_mention_date')
            if next_mention_date:
                next_mention_date = convert_date(next_mention_date)
            plea_taken = request.POST.get('plea_taken')
            application_outcome = request.POST.get('application_outcome')
            court_outcome = request.POST.get(
                'court_outcome') if request.POST.get('court_outcome') else None
            court_orders = request.POST.getlist('court_order')

            if court_session_type == 'STMN':
                court_session_type = 'COURT MENTION'
            if court_session_type == 'STHR':
                court_session_type = 'COURT HEARING'
            if court_session_type == 'STPL':
                court_session_type = 'COURT PLEA'
            if court_session_type == 'STAP':
                court_session_type = 'COURT APPLICATION'

            ovccaseevent = OVCCaseEvents.objects.get(pk=case_event_id)
            ovccaseevent.date_of_event = date_of_court_event
            ovccaseevent.case_event_type_id = court_session_type
            ovccaseevent.case_event_notes = court_notes
            ovccaseevent.case_event_outcome = court_outcome
            ovccaseevent.next_hearing_date = next_hearing_date if next_hearing_date else None
            ovccaseevent.next_mention_date = next_mention_date if next_mention_date else None
            ovccaseevent.plea_taken = plea_taken if plea_taken else None
            ovccaseevent.application_outcome = application_outcome if application_outcome else None
            ovccaseevent.save(update_fields=['date_of_event',
                                             'case_event_type_id',
                                             'case_event_notes',
                                             'case_event_outcome',
                                             'next_hearing_date',
                                             'next_mention_date',
                                             'plea_taken',
                                             'application_outcome'])

            ovccourtorders = OVCCaseEventCourt.objects.filter(
                case_event_id=case_event_id, is_void=False)
            existing_courtorders = []
            new_courtorders = []
            case_event_ids = []

            """ Get existing_courtorders & case_event_ids"""
            if ovccourtorders:
                for ovccourtorder in ovccourtorders:
                    if ovccourtorder.court_order:
                        existing_courtorders.append(
                            str(ovccourtorder.court_order))
                    case_event_ids.append(ovccourtorder.case_event_id_id)

            if court_orders:
                """ Get new_courtorders """
                for i, ncourtorders in enumerate(court_orders):
                    new_courtorders = str(ncourtorders).split(',')

                """ Cater for Unchecked yet Pre-existed """
                if existing_courtorders:
                    for i, ecourtorder in enumerate(existing_courtorders):
                        if not(str(ecourtorder) in new_courtorders):
                            OVCCaseEventCourt.objects.filter(
                                case_event_id=followup_id, court_order=ecourtorder).update(is_void=True)
                else:
                    OVCCaseEventCourt.objects.filter(
                        case_event_id=case_event_id, court_order=None).update(is_void=True)

                """ Cater for new selected court_orders  """
                for i, ncourtorder in enumerate(new_courtorders):
                    if not (str(ncourtorder) in existing_courtorders):
                        OVCCaseEventCourt(
                            court_order=ncourtorder,
                            case_event_id=OVCCaseEvents.objects.get(
                                pk=case_event_ids[0]),
                            case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()
            else:
                ovccourtsessions = OVCCaseEventCourt.objects.filter(
                    case_event_id=case_event_id, court_order=None, is_void=False).update(is_void=True)
                # print ' hapa'
                OVCCaseEventCourt(
                    court_order=None,
                    case_event_id=OVCCaseEvents.objects.get(
                        pk=case_event_ids[0]),
                    case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error editing Court Sessions - %s ' % str(e))
    return HttpResponse('Court Sessions Updated')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_court(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')

            # Update OVCCaseEvents
            ovc_ce = OVCCaseEvents.objects.get(pk=case_event_id)
            ovc_ce.is_void = True
            ovc_ce.save(update_fields=['is_void'])

            # Delete/Void Court Orders Provided
            ovc_court_orders = OVCCaseEventCourt.objects.filter(
                case_event_id=case_event_id)
            for ovc_court_order in ovc_court_orders:
                ovc_court_order.is_void = True
                ovc_court_order.save(update_fields=['is_void'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error deleting Court Sessions - %s ' % str(e))
    return HttpResponse('Court Orders Deleted')


def save_closure(request):
    jsonClosureData = []
    try:
        if request.method == 'POST':
            # Get app_user
            user_id = request.user.id
            # now = timezone.now()

            case_event_id = uuid.uuid4()
            case_id = request.POST.get('case_id')
            # case_status = request.POST.get('case_status')
            # case_status = 'INACTIVE' if case_status == 'AYES' else 'ACTIVE'
            case_outcome = request.POST.get('case_outcome')
            transfered_to = request.POST.get(
                'transfered_to') if request.POST.get('transfered_to') else None
            intervention_list = request.POST.get(
                'intervention_list') if request.POST.get('intervention_list') else None
            case_closure_notes = request.POST.get('case_closure_notes')
            date_of_case_closure = request.POST.get('date_of_case_closure')
            if date_of_case_closure:
                date_of_case_closure = convert_date(date_of_case_closure)

            case_status = 'TRANSFERRED' if case_outcome == 'COTR' else 'INACTIVE'
            transfer_to = RegOrgUnit.objects.get(
                pk=int(transfered_to)) if transfered_to else None

            # OVCCaseEventClosure
            caseevent_ids = OVCCaseEvents.objects.filter(
                case_id=case_id, is_void=False).values_list('case_event_id', flat=True)

            # 1. Deactivate all existing
            ovccaseclosures = OVCCaseEventClosure.objects.filter(
                case_event_id__in=caseevent_ids, is_void=False)
            if ovccaseclosures:
                for ovccaseclosure in ovccaseclosures:
                    ovccaseclosure.is_active = False
                    ovccaseclosure.is_void = True
                    ovccaseclosure.save(update_fields=['is_active'])

            # 2. Save New
            OVCCaseEvents(
                case_event_id=case_event_id,
                case_event_type_id='CLOSURE',
                date_of_event=date_of_case_closure,
                case_event_details='case_event_details',
                case_event_notes='case_outcome_notes',
                case_event_outcome=case_closure_notes,
                next_hearing_date=None,
                case_id=OVCCaseRecord.objects.get(pk=case_id),
                app_user=AppUser.objects.get(pk=user_id)
            ).save()

            # 3. Save interventions if any
            if intervention_list:
                intervention_data = json.loads(intervention_list)
                for intv_data in intervention_data:
                    if intv_data:
                        intervention_grouping_id = uuid.uuid4()
                        intervention = intv_data['intervention']
                        case_category_id = intv_data['case_category']
                        date_of_encounter_event = date_of_case_closure

                        OVCCaseEventServices(
                            # service_id = new_guid_32(),
                            service_provided=intervention,
                            service_provider='EXIT',
                            place_of_service='EXIT',
                            date_of_encounter_event=date_of_encounter_event,
                            service_grouping_id=intervention_grouping_id,
                            case_event_id=OVCCaseEvents.objects.get(
                                pk=case_event_id),
                            case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()

            # 4. Save OVCCaseEventClosure
            OVCCaseEventClosure(
                # case_status=case_status,
                case_outcome=case_outcome,
                transfer_to=transfer_to,
                date_of_case_closure=date_of_case_closure,
                case_closure_notes=case_closure_notes,
                case_event_id=OVCCaseEvents.objects.get(pk=case_event_id),
                is_active=True
            ).save()

            # OVCCaseRecord
            ovccr = OVCCaseRecord.objects.get(pk=case_id)
            ovccr.case_status = case_status
            ovccr.save(update_fields=['case_status'])

            closure_status = 'CLOSED'
            if (ovccr.case_status == 'ACTIVE' or ovccr.case_status == 'TRANSFERRED'):
                closure_status = 'OPEN'

            # jsonClosureData.append({'closure_status': closure_status, 'case_status': ovccr.case_status})
            jsonClosureData.append({'closure_msg': 'Case closure successful'})
            return JsonResponse(jsonClosureData, content_type='application/json',
                        safe=False)
        else:
            print('Not a POST $')
    except Exception as e:
        # print 'Case Close Error: %s' % str(e)
        jsonClosureData.append(
            {'closure_msg': 'Error closing case (%s) - ' + str(e)})
    return JsonResponse(jsonClosureData, content_type='application/json',
                        safe=False)


def edit_closure(request):
    jsonClosureData = []
    try:
        if request.method == 'POST':
            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id
            now = timezone.now()

            case_event_id = request.POST.get('case_event_id')
            case_id = request.POST.get('case_id')
            case_outcome = request.POST.get('case_outcome')
            transfered_to = request.POST.get(
                'transfered_to') if request.POST.get('transfered_to') else None
            intervention_list = request.POST.get(
                'intervention_list') if request.POST.get('intervention_list') else None
            case_closure_notes = request.POST.get('case_closure_notes')
            date_of_case_closure = request.POST.get('date_of_case_closure')
            if date_of_case_closure:
                date_of_case_closure = convert_date(date_of_case_closure)
            case_status = 'TRANSFERRED' if case_outcome == 'COTR' else 'INACTIVE'
            transfer_to = RegOrgUnit.objects.get(
                pk=int(transfered_to)) if transfered_to else None

            # 1. Update OVCCaseEvents
            ovc_ce = OVCCaseEvents.objects.get(pk=case_event_id)
            ovc_ce.case_event_notes = case_closure_notes
            ovc_ce.date_of_event = date_of_case_closure
            ovc_ce.save(update_fields=['date_of_event', 'case_event_notes'])

            # 2. Update OVCCaseEventClosure
            case_events_closure = OVCCaseEventClosure.objects.get(
                case_event_id=case_event_id, is_void=False)
            case_events_closure.case_outcome = case_outcome
            case_events_closure.transfer_to = transfer_to
            case_events_closure.date_of_case_closure = date_of_case_closure
            case_events_closure.case_closure_notes = case_closure_notes
            case_events_closure.save(update_fields=['case_outcome',
                                                    'date_of_case_closure',
                                                    'transfer_to',
                                                    'case_closure_notes'])

            # 3. Update OVCCaseEventServices
            existing_services = []
            new_services = []
            existing_services = OVCCaseEventServices.objects.filter(
                case_event_id=case_event_id).values_list('service_provided', flat=True)

            # 3. Save interventions if any
            if intervention_list:
                intervention_data = json.loads(intervention_list)
                for intv_data in intervention_data:
                    if intv_data:
                        intervention_grouping_id = new_guid_32(),
                        intervention = intv_data['intervention']
                        intervention_status = intv_data['intervention_status']
                        case_category_id = intv_data['case_category']
                        date_of_encounter_event = date_of_case_closure

                        if intervention_status == 'new':
                            OVCCaseEventServices(
                                # service_id = new_guid_32(),
                                service_provided=intervention,
                                service_provider='EXIT',
                                place_of_service='EXIT',
                                date_of_encounter_event=date_of_encounter_event,
                                service_grouping_id=intervention_grouping_id,
                                case_event_id=OVCCaseEvents.objects.get(
                                    pk=case_event_id),
                                case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()

            jsonClosureData.append(
                {'closure_msg': 'Success updating closed case.'})
        else:
            print('Not a POST $')
    except Exception as e:
        jsonClosureData.append(
            {'closure_msg': 'Error updating closed case (%s) - ' + str(e)})
    return JsonResponse(jsonClosureData, content_type='application/json',
                        safe=False)


def view_closure(request):
    ce_resultsets = []
    svc_resultsets = []
    ovc_events = None
    ovc_closure_events = []
    jsonClosureData = []
    ovc_services = []
    ovc_category_ids = []
    jsonCeData = []
    jsonSvcsData = []
    service_grouping_ids = []

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')
            ovc_closure_event = OVCCaseEventClosure.objects.get(
                case_event_id=case_event_id, is_void=False)
            case_outcome = ovc_closure_event.case_outcome

            # Get interventions if Other Outcome (COOT)
            if case_outcome == 'COOT':
                ovc_events_svcs = OVCCaseEventServices.objects.filter(
                    case_event_id=case_event_id, is_void=False)

                """ Get service_grouping_ids[] """
                for ovc_events_svc in ovc_events_svcs:
                    ovc_category_ids.append(
                        str(ovc_events_svc.case_category_id))
                    service_grouping_id = str(
                        ovc_events_svc.service_grouping_id)
                    if not service_grouping_id in service_grouping_ids:
                        service_grouping_ids.append(str(service_grouping_id))

                """ Get Services Provided """
                ovc_events_svcs2 = None
                for service_grouping_id in service_grouping_ids:
                    ovc_events_svcs2 = OVCCaseEventServices.objects.filter(
                        service_grouping_id=service_grouping_id)

                    for ovc_events_svc2 in ovc_events_svcs2:
                        date_of_encounter_event = ovc_events_svc2.date_of_encounter_event
                        if date_of_encounter_event:
                            date_of_encounter_event = date_of_encounter_event.strftime(
                                '%d-%b-%Y')

                        jsonSvcsData.append({
                            'pk': str(ovc_events_svc2.service_id),
                            'service_provided': translate(ovc_events_svc2.service_provided),
                            'service_provided_id': ovc_events_svc2.service_provided,
                            'service_provider': ovc_events_svc2.service_provider,
                            'place_of_service': str(ovc_events_svc2.place_of_service),
                            'date_of_encounter_event': date_of_encounter_event,
                            'service_grouping_id': str(ovc_events_svc2.service_grouping_id)
                        })

                ovc_events = OVCCaseEvents.objects.filter(
                    case_event_id=case_event_id, is_void=False)
                for ovc_event in ovc_events:
                    date_of_event = ovc_event.date_of_event
                    if date_of_event:
                        date_of_event = date_of_event.strftime('%d-%b-%Y')

                    jsonCeData.append({'case_event_id': str(ovc_event.case_event_id),
                                       'case_event_type_id': str(ovc_event.case_event_type_id),
                                       'date_of_event': date_of_event,
                                       'case_event_notes': str(ovc_event.case_event_notes),
                                       'case_category_id': ovc_category_ids[0],
                                       'case_category': translate(translate_case(ovc_category_ids[0])),
                                       'jsonSvcsData': jsonSvcsData
                                       })

            ovc_events = OVCCaseEvents.objects.filter(
                case_event_id=case_event_id, is_void=False)
            for ovc_event in ovc_events:
                case_event_type_id = ovc_event.case_event_type_id
                date_of_event = (ovc_event.date_of_event).strftime('%d-%b-%Y')

                jsonClosureData.append({'case_event_type_id': ovc_event.case_event_type_id,
                                        'case_event_id': str(ovc_event.case_event_id),
                                        'date_of_event': str(ovc_event.date_of_event),
                                        'case_event_notes': str(ovc_event.case_event_notes),
                                        'date_of_event': date_of_event,
                                        'closure_outcome': case_outcome,
                                        'transfer_to': ovc_closure_event.transfer_to_id,
                                        'case_closure_notes': ovc_closure_event.case_closure_notes,
                                        'resultsets': jsonCeData
                                        })
            print('jsonClosureData .... %s' % jsonClosureData)
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error viewing Case Closures - %s ' % str(e))
    return JsonResponse(jsonClosureData, content_type='application/json',
                        safe=False)


def delete_closure(request):
    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('case_event_id')
            case_id = request.POST.get('case_id')

            # print 'case_event_id (%s) and case_id(%s)' % (case_event_id,
            # case_id)

            # update case_events
            case_event = OVCCaseEvents.objects.get(
                case_event_id=case_event_id, is_void=False)
            case_event.is_void = True
            case_event.save(update_fields=['is_void'])

            # update case_events_closure
            case_events_closure = OVCCaseEventClosure.objects.get(
                case_event_id=case_event_id, is_void=False)
            case_events_closure.is_void = True
            case_events_closure.save(update_fields=['is_void'])

            # update case_record
            case_status = 'ACTIVE'
            case_record = OVCCaseRecord.objects.get(pk=case_id)
            case_record.case_status = case_status
            case_record.save(update_fields=['case_status'])

        else:
            print('Not a POST $')
    except Exception as e:
        return HttpResponse('Delete case closure error - %s' % str(e))
    return HttpResponse('Delete case closure success.')


def save_summon(request):
    try:
        if request.method == 'POST':
            case_event_id = new_guid_32()

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            honoured = request.POST.get('honoured')
            honoured = True if honoured == 'AYES' else False
            honoured_date = request.POST.get('honoured_date')
            if honoured_date:
                honoured_date = convert_date(honoured_date)

            summon_date = request.POST.get(
                'summon_date') if request.POST.get('summon_date') else None
            if summon_date:
                summon_date = convert_date(summon_date)

            """
            visit_date = request.POST.get(
                'visit_date') if request.POST.get('visit_date') else None
            if visit_date:
                visit_date = convert_date(visit_date)
            """

            summon_note = request.POST.get(
                'summon_note') if request.POST.get('summon_note') else None
            case_id = request.POST.get(
                'case_id') if request.POST.get('case_id') else None

            date_of_event = honoured_date

            ovccaseevents = OVCCaseEvents(
                case_event_id=case_event_id,
                case_event_type_id='SUMMON',
                date_of_event=date_of_event,
                case_event_details='case_event_details',
                case_event_notes=summon_note,
                case_event_outcome='case_event_outcome',
                next_hearing_date=None,
                case_id=OVCCaseRecord.objects.get(pk=case_id),
                app_user=AppUser.objects.get(pk=user_id)
            )
            ovccaseevents.save()
            summon_fk = ovccaseevents.pk

            OVCCaseEventSummon(
                honoured=honoured,
                honoured_date=honoured_date,
                summon_date=summon_date,
                summon_note=summon_note,
                case_category_id=None,
                case_event_id=OVCCaseEvents.objects.get(
                    pk=summon_fk),
            ).save()

            summon_count = OVCCaseEventSummon.objects.filter(
                case_event_id__case_id_id=case_id, is_void=False).count()
            results = {"summon_count": summon_count,
                       "message": "Save Summons OK"}
        else:
            print('Not POST')
    except Exception as e:
        # return HttpResponse('Error saving Summons - %s ' % str(e))
        results = {"summon_count": 0,
                   "message": "Error saving Summons - %s " % str(e)}
        return JsonResponse(results, safe=False)
    # return HttpResponse('Save Summons OK')
    return JsonResponse(results, safe=False)


def edit_summon(request):
    now = timezone.now()

    try:
        if request.method == 'POST':

            case_id = request.POST.get('case_id')
            case_event_id = request.POST.get('case_event_id')
            honoured = request.POST.get('honoured')
            honoured = True if honoured == 'AYES' else False
            honoured_date = request.POST.get('honoured_date')
            if honoured_date:
                honoured_date = convert_date(honoured_date)

            summon_date = request.POST.get(
                'summon_date') if request.POST.get('summon_date') else None
            if summon_date:
                summon_date = convert_date(summon_date)

            """
            visit_date = request.POST.get(
                'visit_date') if request.POST.get('visit_date') else None
            if visit_date:
                visit_date = convert_date(visit_date)
            """

            summon_note = request.POST.get(
                'summon_note') if request.POST.get('summon_note') else None
            case_id = request.POST.get(
                'case_id') if request.POST.get('case_id') else None

            date_of_event = summon_date if summon_date else honoured_date

            ovccaseevent = OVCCaseEvents.objects.get(pk=case_event_id)
            ovccaseevent.date_of_event = honoured_date
            ovccaseevent.save(update_fields=['date_of_event',
                                             'case_event_notes'])

            ovccaseeventsummon = OVCCaseEventSummon.objects.get(
                case_event_id=case_event_id)
            ovccaseeventsummon.honoured = honoured
            ovccaseeventsummon.honoured_date = honoured_date
            ovccaseeventsummon.summon_date = summon_date
            # ovccaseeventsummon.visit_date = visit_date
            ovccaseeventsummon.summon_note = summon_note
            ovccaseeventsummon.save(update_fields=['honoured',
                                                   'honoured_date',
                                                   'summon_date',
                                                   #'visit_date',
                                                   'summon_note'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error editing sUMMON Sessions - %s ' % str(e))
    return HttpResponse('Summons Updated')


def view_summon(request):
    jsonSummonData = []

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')

            ovc_summon = OVCCaseEventSummon.objects.get(
                case_event_id=case_event_id, is_void=False)
            ovc_event = OVCCaseEvents.objects.get(
                case_event_id=case_event_id, is_void=False)

            honoured_date = ovc_summon.honoured_date
            summon_date = ovc_summon.summon_date
            honoured = ovc_summon.honoured
            honoured = 'AYES' if honoured else 'ANNO'
            date_of_event = (ovc_event.date_of_event).strftime('%d-%b-%Y')
            summon_date = (ovc_summon.summon_date).strftime(
                '%d-%b-%Y') if ovc_summon.summon_date else None
            # visit_date = (ovc_summon.visit_date).strftime('%d-%b-%Y')
            jsonSummonData.append({
                'case_event_id': ovc_event.case_event_id,
                'honoured': honoured,
                'summon_date': summon_date,
                'date_of_event': date_of_event,
                # 'visit_date': visit_date,
                'summon_note': ovc_event.case_event_notes
            })
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error viewing Summons - %s ' % str(e))
    return JsonResponse(jsonSummonData, content_type='application/json',
                        safe=False)


def delete_summon(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')

            # Update OVCCaseEvents
            ovc_ce = OVCCaseEvents.objects.get(pk=case_event_id)
            ovc_ce.is_void = True
            ovc_ce.save(update_fields=['is_void'])

            # Delete/Void Summons Provided
            ovc_summons = OVCCaseEventSummon.objects.filter(
                case_event_id=case_event_id)
            for ovc_summon in ovc_summons:
                ovc_summon.is_void = True
                ovc_summon.save(update_fields=['is_void'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error deleting Summons - %s ' % str(e))
    return HttpResponse('Summons deleted')


def delete_referral(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            referral_id = request.POST.get('referral_id')

            print('referral_id >> %s' % referral_id)

            # Update OVCReferral
            ovc_ref = OVCReferral.objects.get(pk=referral_id)
            ovc_ref.is_void = True
            ovc_ref.save(update_fields=['is_void'])
        else:
            print('Not POST')
    except Exception as e:
        return HttpResponse('Error deleting Referral - %s ' % str(e))
    return HttpResponse('Referral deleted')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def placement(request, id):
    """The view to Placement in institutions."""
    try:
        user_id = request.user.id
        cases = OVCCaseRecord.objects.filter(person_id=id, is_void=False)
        form = ResidentialForm({
            'person_id': id,
            'admission_number': 'XXXX/YYYY',
            'user_id': user_id})
        init_data = RegPerson.objects.filter(pk=id)
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        return render(request, 'forms/new_placement.html',
                      {'form': form, 'cases': cases,
                       'init_data': init_data,
                       'vals': vals})
    except Exception as e:
        print('Load placement error - %s' % str(e))
    form = ResidentialForm()
    return render(request, 'forms/new_placement.html', {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def placement_followup(request, id):
    # Get initial data
    init_data = RegPerson.objects.filter(pk=id)
    now = timezone.now()
    date_of_birth = now.date()
    date_today = now.date()
    for data in init_data:
        date_of_birth = data.date_of_birth
    age = relativedelta(
        date_today, date_of_birth).years if date_of_birth else 0

    # Get Placement Data
    try:
        placementdata = OVCPlacement.objects.get(
            person_id=id, is_active=True, is_void=False)
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        form = ResidentialFollowupForm(
            {'person': id, 'child_age': age,
             'placement_id': placementdata.placement_id})
        return render(request,
                      'forms/placement_followup.html',
                      {'form': form, 'placement': placementdata,
                       'init_data': init_data, 'vals': vals})
    except Exception as e:
        err = 'This child may have been discharged'
        msg = 'Follow-up error - (%s). %s.' % (str(e), err)
        print(msg)
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    else:
        pass

@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def placement_follow_up(request, id):
    # Get Placement Data
    try:
        placement_id = str(id)
        placementdata = OVCPlacement.objects.get(
            placement_id=placement_id,
            is_active=True, is_void=False)
        person_id = placementdata.person_id
        # Get initial data
        init_data = RegPerson.objects.filter(pk=person_id)
        now = timezone.now()
        date_of_birth = now.date()
        date_today = now.date()
        for data in init_data:
            date_of_birth = data.date_of_birth
        age = relativedelta(
            date_today, date_of_birth).years if date_of_birth else 0
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        form = ResidentialFollowupForm(
            {'person': person_id, 'child_age': age,
             'placement_id': placementdata.placement_id})
        return render(request,
                      'forms/placement_followup.html',
                      {'form': form, 'placement': placementdata,
                       'init_data': init_data, 'vals': vals})
    except Exception as e:
        err = 'This child may have been discharged'
        msg = 'Follow-up error - (%s). %s.' % (str(e), err)
        print(msg)
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    else:
        pass


def save_placementfollowup(request):
    placementfollowup_type = None
    now = timezone.now()

    # Get app_user
    username = request.user.get_username()
    app_user = AppUser.objects.get(username=username)
    user_id = request.user.id

    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            person = request.POST.get('person')
            placement_id = request.POST.get('placement_id')

            if (action == 'FFFF'):  # All 4 Initial Followups
                followup_type = request.POST.get('placementfollowup_type')
                followup_outcome = request.POST.get(
                    'placementfollowup_outcome')
                followup_date = request.POST.get('placementfollowup_date')
                placementfollowup_type = translate(
                    followup_type) + ' follow-up '
                if followup_date:
                    followup_date = convert_date(followup_date)
                OVCPlacementFollowUp(
                    followup_type=followup_type,
                    followup_date=followup_date,
                    followup_details=translate(
                        followup_type) + ' Follow-up Done',
                    followup_outcome=followup_outcome,
                    placement_id=OVCPlacement.objects.get(pk=placement_id),
                    person=RegPerson.objects.get(pk=int(person)),
                    created_by=user_id,
                    timestamp_created=now).save()
            if (action == 'SERV'):
                print('Good to save services')
                followup_type = request.POST.get('service_type')
                service_date = request.POST.get('service_date')
                service_outcome = request.POST.get('service_outcome')
                followup_date = convert_date(service_date)
                OVCPlacementFollowUp(
                    followup_type='FUSP',
                    followup_date=followup_date,
                    followup_details=translate(
                        followup_type) + ' Follow-up Done',
                    followup_outcome=service_outcome,
                    placement_id_id=placement_id,
                    person_id=int(person),
                    created_by=user_id,
                    timestamp_created=now).save()

            if (action == 'DIS'):
                placementfollowup_type = 'Discharge follow-up '
                discharge_type = request.POST.get('discharge_type')
                discharge_dest = request.POST.get('discharge_destination')
                disc_destination = discharge_dest if discharge_dest else None
                # actual_return_date = request.POST.get('actual_return_date')

                discharge_date = request.POST.get('discharge_date')
                if discharge_date:
                    discharge_date = convert_date(discharge_date)

                discharge_reason = request.POST.get('discharge_reason')

                expected_return_date = request.POST.get('expected_return_date')
                if expected_return_date:
                    expected_return_date = convert_date(expected_return_date)
                # actual_return_date = request.POST.get('actual_return_date')
                discharge_comments = request.POST.get('discharge_comments')

                # Get Discharge for this person and placement
                disch = OVCDischargeFollowUp.objects.filter(
                    person_id=person, placement_id_id=placement_id)
                if not disch:
                    pobj = RegPerson.objects.get(pk=int(person))
                    OVCDischargeFollowUp(
                        type_of_discharge=discharge_type,
                        discharge_destination=disc_destination,
                        date_of_discharge=discharge_date,
                        reason_of_discharge=discharge_reason,
                        expected_return_date=expected_return_date,
                        actual_return_date=None,
                        discharge_comments=discharge_comments,
                        placement_id=OVCPlacement.objects.get(pk=placement_id),
                        person=pobj,
                        created_by=user_id,
                        timestamp_created=now).save()

                    if disc_destination:
                        print('Notify the receiving SI')
                        ou_id = int(disc_destination)
                        ou_name = request.session.get('ou_primary_name', '')
                        msg = ' has been transfered to your institution'
                        if ou_name:
                            msg += ' from %s.' % (ou_name)
                        names = '%s %s' % (pobj.first_name, pobj.surname)
                        notification = "Child (%s) %s" % (names, msg)
                        send_notification(request, 2, ou_id, notification)
                else:
                    placementfollowup_type = 'Discharge follow-up (Duplicate) '

                # Deactivate OVCPlacement Entries
                OVCPlacement.objects.filter(
                    person=person, pk=placement_id).update(is_active=False)

            if (action == 'EDU'):
                placementfollowup_type = 'Education follow-up '
                admmitted_to_school = request.POST.get('admmitted_to_school')
                not_in_sch = request.POST.get('not_in_school_reason')
                not_in_school_reason = not_in_sch if not_in_sch else None
                name_of_school = request.POST.get(
                    'name_of_school') if request.POST.get('name_of_school') else None
                admmission_type = request.POST.get(
                    'admmission_type') if request.POST.get('admmission_type') else None
                admmission_date = request.POST.get(
                    'admmission_to_school_date') if request.POST.get('admmission_to_school_date') else None
                if admmission_date:
                    admmission_date = convert_date(admmission_date)
                admission_levels = request.POST.getlist(
                    'admmission_class') if request.POST.getlist('admmission_class') else None
                admmission_subclass = request.POST.get(
                    'admmission_subclass') if request.POST.get('admmission_subclass') else None
                education_comments = request.POST.get(
                    'education_comments') if request.POST.get('education_comments') else None

                # Void any existing school info
                existing_ovc_edus = OVCEducationFollowUp.objects.filter(
                    person=person)
                if existing_ovc_edus:
                    for existing_ovc_edu in existing_ovc_edus:
                        existing_ovc_edu.is_void = True
                        existing_ovc_edu.save(update_fields=['is_void'])
                existing_ovc_edus_audit = FormsLog.objects.filter(
                    person=person, form_type_id='FTCB')
                if existing_ovc_edus_audit:
                    for existing_ovc_edu_audit in existing_ovc_edus_audit:
                        existing_ovc_edu_audit.is_void = True
                        existing_ovc_edu_audit.save(update_fields=['is_void'])

                school_id = SchoolList.objects.get(
                    pk=name_of_school) if name_of_school else None
                # Save New
                ovc_edu = OVCEducationFollowUp(
                    admitted_to_school=admmitted_to_school,
                    not_in_school_reason=not_in_school_reason,
                    school_id=school_id,
                    school_admission_type=admmission_type,
                    admission_to_school_date=admmission_date,
                    # admmission_class=admmission_class,
                    # admmission_subclass=admmission_subclass,
                    education_comments=education_comments,
                    created_by=user_id,
                    timestamp_created=now,
                    placement_id=OVCPlacement.objects.get(pk=placement_id),
                    person=RegPerson.objects.get(pk=int(str(person)))
                )
                ovc_edu.save()
                ovc_edu_pk = ovc_edu.pk

                if admission_levels:
                    for i, admission_level in enumerate(admission_levels):
                        admission_level = admission_level.split(',')
                        for level in admission_level:
                            ACVT_levels = ['TVC1', 'TVC2',
                                           'TVC3', 'TVC4', 'TVC5']
                            if level:
                                if level in ACVT_levels:
                                    OVCEducationLevelFollowUp(
                                        admission_level=level,
                                        admission_sublevel=admmission_subclass,
                                        education_followup_id=OVCEducationFollowUp.objects.get(
                                            pk=ovc_edu_pk),
                                        timestamp_created=now).save()
                                else:
                                    OVCEducationLevelFollowUp(
                                        admission_level=level,
                                        admission_sublevel=None,
                                        education_followup_id=OVCEducationFollowUp.objects.get(
                                            pk=ovc_edu_pk),
                                        timestamp_created=now).save()

            if (action == 'ADV'):
                placementfollowup_type = 'Adverse events follow-up '
                adverse_events = request.POST.get('adverse_events')
                attendance_type = request.POST.get('attendance_type')
                hospital_referral_type = request.POST.get(
                    'hospital_referral_type')
                adverse_event_date = request.POST.get('adverse_event_date')
                if adverse_event_date:
                    adverse_event_date = convert_date(adverse_event_date)
                adverse_medical_events = request.POST.getlist(
                    'adverse_medical_events')
                adverse_offences = request.POST.getlist('adverse_offences')
                adverse_event_id = str(adverse_events)
                old_events = OVCAdverseEventsFollowUp.objects.filter(
                    placement_id_id=placement_id, is_void=False,
                    adverse_condition_description=adverse_event_id)
                if old_events and adverse_event_id in ['AEAB', 'AEDE', 'AEES']:
                    print('This can not happen twice - %s' % (adverse_event_id))
                    placementfollowup_type = 'Adverse events (Duplicate entry) follow-up NOT '
                else:
                    ovc_adverse = OVCAdverseEventsFollowUp(
                        adverse_condition_id=new_guid_32(),
                        adverse_condition_description=adverse_events,
                        attendance_type=attendance_type,
                        referral_type=hospital_referral_type,
                        adverse_event_date=adverse_event_date,
                        placement_id=OVCPlacement.objects.get(pk=placement_id),
                        person=RegPerson.objects.get(pk=int(person)),
                        created_by=user_id,
                        timestamp_created=now)
                    ovc_adverse.save()
                    ovc_adverse_pk = ovc_adverse.pk

                    # If this adverse event is abduction, Escape or Death do Discharge
                    adv_events = {'AEAB': 'Abducted', 'AEDE': 'Died', 'AEES': 'Escaped'}
                    if adverse_event_id in ['AEAB', 'AEDE', 'AEES']:
                        print('Adverse Event for Discharge %s' % (adverse_event_id))
                        disc_reason = 'Child %s' % (adv_events[adverse_event_id])                    
                        pobj = RegPerson.objects.get(pk=int(person))
                        placement_obj = OVCPlacement.objects.get(pk=placement_id)
                        OVCDischargeFollowUp(
                            type_of_discharge=adverse_event_id,
                            discharge_destination=None,
                            date_of_discharge=adverse_event_date,
                            reason_of_discharge=disc_reason,
                            expected_return_date=None,
                            actual_return_date=None,
                            discharge_comments='Adverse Event',
                            placement_id=placement_obj,
                            person=pobj,
                            created_by=user_id,
                            timestamp_created=now).save()
                        placement_obj.is_active=False
                        placement_obj.save()

                    if adverse_medical_events:
                        for i, medical_events in enumerate(adverse_medical_events):
                            medical_events = medical_events.split(',')
                            for medical_event in medical_events:
                                OVCAdverseEventsOtherFollowUp(
                                    adverse_condition=medical_event,
                                    adverse_condition_id=OVCAdverseEventsFollowUp.objects.get(
                                        pk=ovc_adverse_pk),
                                    timestamp_created=now).save()

                    if adverse_offences:
                        for i, offence_events in enumerate(adverse_offences):
                            offence_events = offence_events.split(',')
                            for offence_event in offence_events:
                                OVCAdverseEventsOtherFollowUp(
                                    adverse_condition=offence_event,
                                    adverse_condition_id=OVCAdverseEventsFollowUp.objects.get(
                                        pk=ovc_adverse_pk),
                                    timestamp_created=now).save()
            if (action == 'COT'):
                placementfollowup_type = 'Court sessions follow-up '
                case_event_id = new_guid_32()

                # Get app_user
                username = request.user.get_username()
                app_user = AppUser.objects.get(username=username)
                user_id = app_user.id

                case_category_id = request.POST.get('court_session_case')
                court_session_type = request.POST.get('court_session_type')
                date_of_court_event = request.POST.get('date_of_court_event')
                if date_of_court_event:
                    date_of_court_event = convert_date(date_of_court_event)
                court_notes = request.POST.get('court_notes')
                next_hearing_date = request.POST.get('next_hearing_date')
                if next_hearing_date:
                    next_hearing_date = convert_date(next_hearing_date)
                court_session_type = request.POST.get('court_session_type')
                plea_taken = request.POST.get(
                    'plea_taken') if request.POST.get('plea_taken') else None
                application_outcome = request.POST.get(
                    'application_outcome') if request.POST.get('application_outcome') else None
                next_mention_date = request.POST.get('next_mention_date')
                if next_mention_date:
                    next_mention_date = convert_date(next_mention_date)
                court_outcome = request.POST.get('court_outcome')
                court_orders = request.POST.getlist('court_order')

                case_id = None
                casecategory = OVCCaseCategory.objects.get(pk=case_category_id)
                if casecategory:
                    case_id = OVCCaseRecord.objects.get(
                        pk=casecategory.case_id_id)

                # court_session_type = 'COURT MENTION'
                # if court_session_type == 'STMN' else 'COURT HEARING'

                if court_session_type == 'STMN':
                    court_session_type = 'COURT MENTION'
                if court_session_type == 'STHR':
                    court_session_type = 'COURT HEARING'
                if court_session_type == 'STPL':
                    court_session_type = 'COURT PLEA'
                if court_session_type == 'STAP':
                    court_session_type = 'COURT APPLICATION'

                OVCCaseEvents(
                    case_event_id=case_event_id,
                    case_event_type_id=court_session_type,
                    date_of_event=date_of_court_event,
                    case_event_details='case_event_details',
                    case_event_notes=court_notes,
                    case_event_outcome=court_outcome,
                    next_hearing_date=next_hearing_date,
                    next_mention_date=next_mention_date,
                    plea_taken=plea_taken,
                    application_outcome=application_outcome,
                    case_id=case_id,
                    placement_id=OVCPlacement.objects.get(pk=placement_id),
                    app_user=AppUser.objects.get(pk=user_id)
                ).save()

                if court_orders:
                    for i, court_order in enumerate(court_orders):
                        court_order = court_order.split(',')
                        for order in court_order:
                            OVCCaseEventCourt(
                                court_order=order,
                                case_event_id=OVCCaseEvents.objects.get(
                                    pk=case_event_id),
                                case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()
                else:
                    OVCCaseEventCourt(
                        court_order=None,
                        case_event_id=OVCCaseEvents.objects.get(
                            pk=case_event_id),
                        case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()

    except Exception as e:
        return HttpResponse('(%s)' % str(e))
        print('Error saving Court Sessions - %s' % str(e))
    return HttpResponse(placementfollowup_type)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_placementfollowup(request):
    jsonPlacementEventsData = []
    try:
        if request.method == 'POST':
            person = request.POST.get('person')
            followup_id = request.POST.get('followup_id')
            followup_type = request.POST.get('followup_type')

            # ITP/Tracing/Case Conferencing/Home Visit
            if (followup_type == 'FFFF'):
                followup1_data = OVCPlacementFollowUp.objects.get(
                    pk=followup_id)

                # Convert Dates
                followup_date = followup1_data.followup_date
                if followup_date:
                    followup_date = followup_date.strftime('%d-%b-%Y')

                jsonPlacementEventsData.append({
                    'pk': followup1_data.placememt_followup_id,
                    'person_id': followup1_data.person_id,
                    'followup_type': followup1_data.followup_type,
                    'followup_date': followup_date,
                    'followup_details': followup1_data.followup_details,
                    'followup_outcome': followup1_data.followup_outcome
                })

            # Education
            if (followup_type == 'Education'):
                ovceducationfollowup = OVCEducationFollowUp.objects.get(
                    pk=followup_id)

                # Convert Dates
                admission_to_school_date = ovceducationfollowup.admission_to_school_date
                if admission_to_school_date:
                    admission_to_school_date = admission_to_school_date.strftime(
                        '%d-%b-%Y')

                admission_levels = []
                admission_sublevels = []
                ovceducationlevelfollowups = OVCEducationLevelFollowUp.objects.filter(
                    education_followup_id=followup_id, is_void=False)
                for ovceducationlevelfollowup in ovceducationlevelfollowups:
                    admission_levels.append(
                        str(ovceducationlevelfollowup.admission_level))
                    admission_sublevels.append(
                        str(ovceducationlevelfollowup.admission_sublevel))

                jsonPlacementEventsData.append({
                    'pk': str(ovceducationfollowup.education_followup_id),
                    'person_id': ovceducationfollowup.person_id,
                    'admitted_to_school': ovceducationfollowup.admitted_to_school,
                    'not_in_school_reason': ovceducationfollowup.not_in_school_reason,
                    'school_admission_type': ovceducationfollowup.school_admission_type,
                    'admission_to_school_date': admission_to_school_date,
                    'admission_level': admission_levels,
                    'admission_sublevel': admission_sublevels,
                    'education_comments': ovceducationfollowup.education_comments,
                    'school_id': str(ovceducationfollowup.school_id_id)
                })

            # Court
            courtevents = ['Court Mention', 'Court Hearing',
                           'Court Plea', 'Court Application']
            if (followup_type in courtevents):
                ovccaseevent = OVCCaseEvents.objects.get(pk=followup_id)

                # Convert Dates
                date_of_event = ovccaseevent.date_of_event
                if date_of_event:
                    date_of_event = date_of_event.strftime('%d-%b-%Y')
                next_hearing_date = ovccaseevent.next_hearing_date
                if next_hearing_date:
                    next_hearing_date = next_hearing_date.strftime('%d-%b-%Y')

                next_mention_date = ovccaseevent.next_mention_date
                if next_mention_date:
                    next_mention_date = next_mention_date.strftime('%d-%b-%Y')

                plea_taken = ovccaseevent.plea_taken
                application_outcome = ovccaseevent.application_outcome

                case_event_type_id = ovccaseevent.case_event_type_id

                ovccourtsessions = OVCCaseEventCourt.objects.filter(
                    case_event_id=followup_id)

                casecategories = []
                if ovccourtsessions:
                    for ovccourtsession in ovccourtsessions:
                        if not str(ovccourtsession.case_category_id) in casecategories:
                            casecategories.append(
                                str(ovccourtsession.case_category_id))

                    courtsessions = []
                    for ovccourtsession in ovccourtsessions:
                        if ovccourtsession.court_order:
                            courtsessions.append(
                                str(ovccourtsession.court_order))
                        else:
                            if ovccaseevent.next_hearing_date:
                                courtsessions.append('Court Adjournment')
                            else:
                                courtsessions.append('Court Mention')

                    # followup_type = 'COURT MENTION' 
                    # if followup3data.case_event_type_id == 'STMN' else 'COURT HEARING'
                    if case_event_type_id == 'COURT MENTION':
                        case_event_type_id = 'STMN'
                    if case_event_type_id == 'COURT HEARING':
                        case_event_type_id = 'STHR'
                    if case_event_type_id == 'COURT PLEA':
                        case_event_type_id = 'STPL'
                    if case_event_type_id == 'COURT APPLICATION':
                        case_event_type_id = 'STAP'

                    jsonPlacementEventsData.append({
                        'pk': ovccaseevent.case_event_id,
                        # 'person_id': ovccaseevent.person_id,
                        'case_event_type_id': case_event_type_id,
                        'date_of_event': date_of_event,
                        'case_event_details': ovccaseevent.case_event_details,
                        'case_event_notes': ovccaseevent.case_event_notes,
                        'case_event_outcome': ovccaseevent.case_event_outcome,
                        'next_hearing_date': next_hearing_date,
                        'next_mention_date': next_mention_date,
                        'plea_taken': plea_taken,
                        'application_outcome': application_outcome,
                        'case_category': casecategories[0],
                        'court_order': courtsessions
                    })

            # Adverse Events
            if (followup_type == 'Adverse Events'):
                ovcadverseevent = OVCAdverseEventsFollowUp.objects.get(
                    pk=followup_id)
                adverse_event_date = ovcadverseevent.adverse_event_date
                if adverse_event_date:
                    adverse_event_date = adverse_event_date.strftime(
                        '%d-%b-%Y')

                ovcadverseotherevents = OVCAdverseEventsOtherFollowUp.objects.filter(
                    adverse_condition_id=followup_id)

                if ovcadverseotherevents:
                    adverseotherevents = []
                    for ovcadverseotherevent in ovcadverseotherevents:
                        adverseotherevents.append(
                            str(ovcadverseotherevent.adverse_condition))

                    jsonPlacementEventsData.append({
                        'pk': ovcadverseevent.adverse_condition_id,
                        'person_id': ovcadverseevent.person_id,
                        'adverse_condition_description': ovcadverseevent.adverse_condition_description,
                        'adverse_event_date': adverse_event_date,
                        'adverse_other_events': adverseotherevents,
                        'attendance_type': ovcadverseevent.attendance_type,
                        'referral_type': ovcadverseevent.referral_type
                    })
                else:
                    jsonPlacementEventsData.append({
                        'pk': ovcadverseevent.adverse_condition_id,
                        'person_id': ovcadverseevent.person_id,
                        'adverse_condition_description': ovcadverseevent.adverse_condition_description,
                        'adverse_event_date': adverse_event_date,
                        'adverse_other_events': '',
                        'attendance_type': ovcadverseevent.attendance_type,
                        'referral_type': ovcadverseevent.referral_type
                    })

            # Discharge
            if (followup_type == 'Discharge'):
                ovcdischargefollowup = OVCDischargeFollowUp.objects.get(
                    pk=followup_id)

                # Convert Dates
                date_of_discharge = ovcdischargefollowup.date_of_discharge
                if date_of_discharge:
                    date_of_discharge = date_of_discharge.strftime('%d-%b-%Y')

                jsonPlacementEventsData.append({
                    'pk': ovcdischargefollowup.discharge_followup_id,
                    'person_id': ovcdischargefollowup.person_id,
                    'type_of_discharge': ovcdischargefollowup.type_of_discharge,
                    'date_of_discharge': date_of_discharge,
                    'discharge_destination': ovcdischargefollowup.discharge_destination,
                    'reason_of_discharge': ovcdischargefollowup.reason_of_discharge,
                    'expected_return_date': ovcdischargefollowup.expected_return_date,
                    'actual_return_date': ovcdischargefollowup.actual_return_date,
                    'discharge_comments': ovcdischargefollowup.discharge_comments
                })
    except Exception as e:
        print('Residential Placement Followup View Error: %s' % str(e))
    return JsonResponse(jsonPlacementEventsData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_placementfollowup(request):
    placementfollowup_type = None
    now = timezone.now()
    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            person = request.POST.get('person')
            followup_id = request.POST.get('placementfollowup_id')

            # All 4 Initial Followups
            if (action == 'FFFF'):
                followup_type = request.POST.get('placementfollowup_type')
                # followup_details = request.POST.get('placementfollowup_details')
                followup_outcome = request.POST.get(
                    'placementfollowup_outcome')
                followup_date = request.POST.get('placementfollowup_date')
                placementfollowup_type = translate(followup_type)
                if followup_date:
                    followup_date = convert_date(followup_date)

                ovcplcmnt = OVCPlacementFollowUp.objects.get(
                    placememt_followup_id=followup_id)
                ovcplcmnt.followup_type = followup_type
                # ovcplcmnt.followup_details = followup_details
                ovcplcmnt.followup_outcome = followup_outcome
                ovcplcmnt.followup_date = followup_date
                ovcplcmnt.save(update_fields=['followup_type',
                                              #'followup_details',
                                              'followup_outcome',
                                              'followup_date'])
            # Education
            if(action == 'EDU'):
                placementfollowup_type = 'Education follow-up '
                admmitted_to_school = request.POST.get('admmitted_to_school')
                not_in_school_reason = request.POST.get(
                    'not_in_school_reason') if request.POST.get('not_in_school_reason') else None
                name_of_school = request.POST.get(
                    'name_of_school') if request.POST.get('name_of_school') else None
                admmission_type = request.POST.get(
                    'admmission_type') if request.POST.get('admmission_type') else None
                admmission_date = request.POST.get('admmission_to_school_date') if request.POST.get(
                    'admmission_to_school_date') else None
                if admmission_date:
                    admmission_date = convert_date(admmission_date)
                admission_levels = request.POST.getlist(
                    'admmission_class') if request.POST.getlist('admmission_class') else None
                admission_sublevel = request.POST.get(
                    'admmission_subclass') if request.POST.get('admmission_subclass') else None
                education_comments = request.POST.get(
                    'education_comments') if request.POST.get('education_comments') else None

                ovceducationfollowup = OVCEducationFollowUp.objects.get(
                    pk=followup_id)
                ovceducationfollowup.admitted_to_school = admmitted_to_school
                ovceducationfollowup.not_in_school_reason = not_in_school_reason
                ovceducationfollowup.school_id = SchoolList.objects.get(
                    pk=name_of_school) if name_of_school else None
                ovceducationfollowup.school_admission_type = admmission_type
                ovceducationfollowup.admission_to_school_date = admmission_date
                ovceducationfollowup.education_comments = education_comments
                ovceducationfollowup.save(update_fields=['admitted_to_school',
                                                         'not_in_school_reason',
                                                         'school_id',
                                                         'school_admission_type',
                                                         'admission_to_school_date',
                                                         'education_comments'])

                if admission_levels:
                    ovceducationlevels = OVCEducationLevelFollowUp.objects.filter(
                        education_followup_id=followup_id, is_void=False)
                    existing_educationlevels = []
                    new_educationlevels = []
                    educationlevels = []
                    education_followup_ids = []

                    """ Get existing_educationlevels & education_followup_ids"""
                    for ovceducationlevel in ovceducationlevels:
                        if ovceducationlevel.admission_level:
                            existing_educationlevels.append(
                                str(ovceducationlevel.admission_level))
                        education_followup_ids.append(
                            str(ovceducationlevel.education_followup_id_id))

                    """ Get new_educationlevels """
                    for i, nadmissionlevels in enumerate(admission_levels):
                        new_educationlevels = str(nadmissionlevels).split(',')

                    """ Cater for Unchecked yet Pre-existed """
                    if existing_educationlevels:
                        for i, eadmissionlevels in enumerate(existing_educationlevels):
                            if not(str(eadmissionlevels) in new_educationlevels):
                                OVCEducationLevelFollowUp.objects.filter(
                                    education_followup_id=followup_id, admission_level=eadmissionlevels).update(is_void=True)

                    print('new_educationlevels - %s' % new_educationlevels)
                    print('existing_educationlevels - %s' % existing_educationlevels)

                    """ Cater for new selected admission_levels  """
                    ACVT_levels = ['TVC1', 'TVC2', 'TVC3', 'TVC4', 'TVC5']
                    for i, nadmissionlevels in enumerate(new_educationlevels):
                        if not (str(nadmissionlevels) in existing_educationlevels):
                            if nadmissionlevels in ACVT_levels:
                                OVCEducationLevelFollowUp(
                                    admission_level=nadmissionlevels,
                                    admission_sublevel=admission_sublevel,
                                    education_followup_id=OVCEducationFollowUp.objects.get(
                                        pk=followup_id),
                                    timestamp_created=now).save()
                            else:
                                OVCEducationLevelFollowUp(
                                    admission_level=nadmissionlevels,
                                    admission_sublevel=None,
                                    education_followup_id=OVCEducationFollowUp.objects.get(
                                        pk=followup_id),
                                    timestamp_created=now).save()
                        ##### Pending work - Update Sublevels #####

            # Court
            if(action == 'COT'):
                placementfollowup_type = 'Court follow-up '
                case_category_id = request.POST.get('court_session_case')
                court_session_type = request.POST.get('court_session_type')
                date_of_court_event = request.POST.get('date_of_court_event')
                if date_of_court_event:
                    date_of_court_event = convert_date(date_of_court_event)
                court_notes = request.POST.get('court_notes')
                next_hearing_date = request.POST.get('next_hearing_date')
                if next_hearing_date:
                    next_hearing_date = convert_date(next_hearing_date)
                court_session_type = request.POST.get('court_session_type')
                plea_taken = request.POST.get('plea_taken')
                application_outcome = request.POST.get('application_outcome')
                next_mention_date = request.POST.get('next_mention_date')
                if next_mention_date:
                    next_mention_date = convert_date(next_mention_date)
                court_outcome = request.POST.get(
                    'court_outcome') if request.POST.get('court_outcome') else None
                court_orders = request.POST.getlist('court_order')

                # court_session_type = 'COURT MENTION' if court_session_type == 'STMN' else 'COURT HEARING'

                if court_session_type == 'STMN':
                    court_session_type = 'COURT MENTION'
                if court_session_type == 'STHR':
                    court_session_type = 'COURT HEARING'
                if court_session_type == 'STPL':
                    court_session_type = 'COURT PLEA'
                if court_session_type == 'STAP':
                    court_session_type = 'COURT APPLICATION'

                ovccaseevent = OVCCaseEvents.objects.get(pk=followup_id)
                ovccaseevent.date_of_event = date_of_court_event
                ovccaseevent.case_event_type_id = court_session_type
                ovccaseevent.case_event_notes = court_notes
                ovccaseevent.case_event_outcome = court_outcome
                ovccaseevent.next_hearing_date = next_hearing_date if next_hearing_date else None
                ovccaseevent.next_mention_date = next_mention_date if next_mention_date else None
                ovccaseevent.plea_taken = plea_taken if plea_taken else None
                ovccaseevent.application_outcome = application_outcome if application_outcome else None
                ovccaseevent.save(update_fields=['date_of_event',
                                                 'case_event_type_id',
                                                 'case_event_notes',
                                                 'case_event_outcome',
                                                 'next_hearing_date',
                                                 'next_mention_date',
                                                 'plea_taken',
                                                 'application_outcome'])

                ovccourtorders = OVCCaseEventCourt.objects.filter(
                    case_event_id=followup_id, is_void=False)
                existing_courtorders = []
                new_courtorders = []
                case_event_ids = []

                """ Get existing_courtorders & case_event_ids"""
                if ovccourtorders:
                    for ovccourtorder in ovccourtorders:
                        if ovccourtorder.court_order:
                            existing_courtorders.append(
                                str(ovccourtorder.court_order))
                        case_event_ids.append(ovccourtorder.case_event_id_id)

                if court_orders:
                    """ Get new_courtorders """
                    for i, ncourtorders in enumerate(court_orders):
                        new_courtorders = str(ncourtorders).split(',')

                    """ Cater for Unchecked yet Pre-existed """
                    if existing_courtorders:
                        for i, ecourtorder in enumerate(existing_courtorders):
                            if not(str(ecourtorder) in new_courtorders):
                                OVCCaseEventCourt.objects.filter(
                                    case_event_id=followup_id, court_order=ecourtorder).update(is_void=True)
                    else:
                        OVCCaseEventCourt.objects.filter(
                            case_event_id=followup_id, court_order=None).update(is_void=True)

                    """ Cater for new selected court_orders  """
                    for i, ncourtorder in enumerate(new_courtorders):
                        if not (str(ncourtorder) in existing_courtorders):
                            OVCCaseEventCourt(
                                court_order=ncourtorder,
                                case_event_id=OVCCaseEvents.objects.get(
                                    pk=case_event_ids[0]),
                                case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()
                else:
                    ovccourtsessions = OVCCaseEventCourt.objects.filter(
                        case_event_id=followup_id, is_void=False).exclude(court_order=None).update(is_void=True)
                    OVCCaseEventCourt(
                        court_order=None,
                        case_event_id=OVCCaseEvents.objects.get(
                            pk=case_event_ids[0]),
                        case_category=OVCCaseCategory.objects.get(pk=case_category_id)).save()

            # Adverse Events
            if(action == 'ADV'):
                placementfollowup_type = 'Adverse events follow-up '
                adverse_events = request.POST.get('adverse_events')
                attendance_type = request.POST.get('attendance_type')
                hospital_referral_type = request.POST.get(
                    'hospital_referral_type')
                adverse_event_date = request.POST.get('adverse_event_date')
                if adverse_event_date:
                    adverse_event_date = convert_date(adverse_event_date)
                adverse_medical_events = request.POST.getlist(
                    'adverse_medical_events')
                adverse_offences = request.POST.getlist('adverse_offences')

                ovcadverseevent = OVCAdverseEventsFollowUp.objects.get(
                    pk=followup_id)
                ovcadverseevent.adverse_condition_description = adverse_events
                ovcadverseevent.attendance_type = attendance_type
                ovcadverseevent.referral_type = hospital_referral_type
                ovcadverseevent.adverse_event_date = adverse_event_date
                ovcadverseevent.save(update_fields=['adverse_condition_description',
                                                    'adverse_event_date',
                                                    'attendance_type',
                                                    'referral_type'])

                ovcadverseotherevents = OVCAdverseEventsOtherFollowUp.objects.filter(
                    adverse_condition_id=followup_id, is_void=False)
                new_medicalevents = []
                new_adverseoffences = []
                existing_medicalevents = []
                existing_adverseoffences = []

                if adverse_medical_events:
                    """ Get new_medicalevents """
                    for i, nmedicalevents in enumerate(adverse_medical_events):
                        new_medicalevents = str(nmedicalevents).split(',')

                    """ Get existing_medicalevents """
                    if ovcadverseotherevents:
                        for ovcadverseotherevent in ovcadverseotherevents:
                            existing_medicalevents.append(
                                str(ovcadverseotherevent.adverse_condition))

                    """ Cater for Unchecked yet Pre-existed """
                    for i, emedicalevent in enumerate(existing_medicalevents):
                        if not(str(emedicalevent) in new_medicalevents):
                            OVCAdverseEventsOtherFollowUp.objects.filter(
                                adverse_condition_id=followup_id, adverse_condition=emedicalevent).update(is_void=True)

                    """ Cater for new selected medicalevents  """
                    for i, nmedicalevent in enumerate(new_medicalevents):
                        if not (str(nmedicalevent) in existing_medicalevents):
                            OVCAdverseEventsOtherFollowUp(
                                adverse_condition=nmedicalevent,
                                adverse_condition_id=OVCAdverseEventsFollowUp.objects.get(
                                    pk=followup_id),
                                timestamp_created=now).save()

                if adverse_offences:
                    """ Get new_adverseoffences """
                    for i, nadverseoffence in enumerate(adverse_offences):
                        new_adverseoffences = str(nadverseoffence).split(',')

                    """ Get existing_adverseoffences """
                    if ovcadverseotherevents:
                        for ovcadverseotherevent in ovcadverseotherevents:
                            existing_adverseoffences.append(
                                str(ovcadverseotherevent.adverse_condition))

                    """ Cater for Unchecked yet Pre-existed """
                    for i, eadverseoffence in enumerate(existing_adverseoffences):
                        if not(str(eadverseoffence) in new_adverseoffences):
                            OVCAdverseEventsOtherFollowUp.objects.filter(
                                adverse_condition_id=followup_id, adverse_condition=eadverseoffence).update(is_void=True)
                    """ Cater for new selected adverseoffences  """
                    for i, nadverseoffence in enumerate(new_adverseoffences):
                        if not (str(nadverseoffence) in existing_adverseoffences):
                            OVCAdverseEventsOtherFollowUp(
                                adverse_condition=nadverseoffence,
                                adverse_condition_id=OVCAdverseEventsFollowUp.objects.get(
                                    pk=followup_id),
                                timestamp_created=now).save()

            # Discharge
            if(action == 'DIS'):
                placementfollowup_type = 'Discharge follow-up '
                discharge_type = request.POST.get('discharge_type')
                discharge_destination = request.POST.get(
                    'discharge_destination') if request.POST.get('discharge_destination') else None
                # actual_return_date = request.POST.get('actual_return_date')

                discharge_date = request.POST.get('discharge_date')
                if discharge_date:
                    discharge_date = convert_date(discharge_date)

                discharge_reason = request.POST.get('discharge_reason')

                expected_return_date = request.POST.get('expected_return_date')
                if expected_return_date:
                    expected_return_date = convert_date(expected_return_date)
                # actual_return_date = request.POST.get('actual_return_date')
                discharge_comments = request.POST.get('discharge_comments')

                ovcdischargefollowup = OVCDischargeFollowUp.objects.get(
                    pk=followup_id)
                ovcdischargefollowup.type_of_discharge = discharge_type
                ovcdischargefollowup.date_of_discharge = discharge_date
                ovcdischargefollowup.discharge_destination = discharge_destination
                ovcdischargefollowup.reason_of_discharge = discharge_reason
                ovcdischargefollowup.expected_return_date = expected_return_date
                ovcdischargefollowup.discharge_comments = discharge_comments
                ovcdischargefollowup.save(update_fields=['type_of_discharge',
                                                         'date_of_discharge',
                                                         'discharge_destination',
                                                         'reason_of_discharge',
                                                         'expected_return_date',
                                                         'discharge_comments'])
    except Exception as e:
        return HttpResponse('(%s)' % str(e))
    return HttpResponse(placementfollowup_type)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_placementfollowup(request):
    placementfollowup_type = None
    now = timezone.now()
    try:
        if request.method == 'POST':
            pk = request.POST.get('pk')
            person = request.POST.get('person')
            followup_type = request.POST.get('followup_type')
            placementfollowup_type = followup_type

            # ITP/Tracing/Case Conferencing/Home Visit
            first4followups = ['Individual Treatment Plan',
                               'Case Conferencing', 'Home Visit', 'Tracing', 'Individual Care Plan', 'Foster Care']
            if (followup_type in first4followups):
                ovcplacementfollowup = OVCPlacementFollowUp.objects.get(pk=pk)
                ovcplacementfollowup.is_void = True
                ovcplacementfollowup.save(
                    update_fields=['is_void'])

            # Education
            if followup_type == 'Education':
                ovceducationfollowup = OVCEducationFollowUp.objects.get(pk=pk)
                ovceducationfollowup.is_void = True
                ovceducationfollowup.save(
                    update_fields=['is_void'])

            # Court
            courtevents = ['Court Mention', 'Court Hearing',
                           'Court Plea', 'Court Application']
            if (followup_type in courtevents):
                ovccourtsessions = OVCCaseEventCourt.objects.filter(
                    case_event_id=pk)
                if ovccourtsessions:
                    for ovccourtsession in ovccourtsessions:
                        ovccourtsession.is_void = True
                        ovccourtsession.save(
                            update_fields=['is_void'])
                ovccaseevent = OVCCaseEvents.objects.get(pk=pk)
                ovccaseevent.is_void = True
                ovccaseevent.save(
                    update_fields=['is_void'])

            # Adverse Events
            if followup_type == 'Adverse Events':
                ovcadversemedicalevents = OVCAdverseEventsOtherFollowUp.objects.filter(
                    adverse_condition_id=pk)
                if ovcadversemedicalevents:
                    for ovcadversemedicalevent in ovcadversemedicalevents:
                        ovcadversemedicalevent.is_void = True
                        ovcadversemedicalevent.save(
                            update_fields=['is_void'])
                ovcadverseevent = OVCAdverseEventsFollowUp.objects.get(pk=pk)
                ovcadverseevent.is_void = True
                ovcadverseevent.save(
                    update_fields=['is_void'])

            # Discharge
            if followup_type == 'Discharge':
                ovcdischargefollowup = OVCDischargeFollowUp.objects.get(pk=pk)
                ovcdischargefollowup.is_void = True
                ovcdischargefollowup.save(
                    update_fields=['is_void'])
                # Activate OVCPlacement Entries
                OVCPlacement.objects.filter(
                    person=person).update(is_active=True)
    except Exception as e:
        return HttpResponse('Error - %s ' % str(e))
    return HttpResponse(placementfollowup_type + ' follow-up ')


def save_placement(request):
    # Get logged in user
    username = request.user.get_username()
    app_user = AppUser.objects.get(username=username)
    placement_pk = ''

    try:
        if request.method == 'POST':
            admission_number = request.POST.get('admission_number')
            # child_lastname = request.POST.get('child_lastname')
            # child_surname = request.POST.get('child_surname')
            # child_gender = request.POST.get('child_gender')
            # child_dob = request.POST.get('child_dob')
            residential_institution_name = request.POST.get(
                'residential_institution_name')
            admission_date = request.POST.get('admission_date')
            transfer_from = request.POST.get(
                'transfer_from') if request.POST.get('transfer_from') else None
            admission_type = request.POST.get('admission_type')
            admission_reason = request.POST.get('admission_reason')
            has_court_committal_order = request.POST.get(
                'has_court_committal_order')
            holding_period = request.POST.get(
                'holding_period') if request.POST.get('holding_period') else None
            court_order_number = request.POST.get(
                'court_order_number') if request.POST.get('court_order_number') else None
            court_order_issue_date = request.POST.get(
                'court_order_issue_date') if request.POST.get('court_order_issue_date') else None
            committing_court = request.POST.get(
                'committing_court') if request.POST.get('committing_court') else None
            committing_period_units = request.POST.get(
                'committing_period_units') if request.POST.get('committing_period_units') else None
            committing_period = request.POST.get(
                'committing_period') if request.POST.get('committing_period') else None
            ob_number = request.POST.get(
                'ob_number') if request.POST.get('ob_number') else None
            free_for_adoption = request.POST.get('free_for_adoption')
            workforce_member_plcmnt = request.POST.get(
                'workforce_member_plcmnt')
            placement_notes = request.POST.get('placement_notes')
            placement_type = request.POST.get('placement_type')
            person_id = request.POST.get('person_id')
            case_record_id = request.POST.get('case_record_id', None)
            now = timezone.now()
            reg_person_pk = int(person_id)
            ou_pk = int(residential_institution_name)

            cur_placement = get_placement(request, ou_pk, reg_person_pk)
            if cur_placement:
                msg = 'Child Already Placed. Go to follow ups.'
                messages.add_message(request, messages.INFO, msg)
                return HttpResponseRedirect(reverse(forms_registry))
            # Convert dates
            if admission_date:
                admission_date = convert_date(admission_date)
            else:
                admission_date = None

            if court_order_issue_date:
                court_order_issue_date = convert_date(court_order_issue_date)
            else:
                court_order_issue_date = None

            # OVCPlacement
            try:
                # Void all other placements
                OVCPlacement.objects.filter(
                    residential_institution_name=residential_institution_name,
                    person_id=person_id, is_void=False).update(is_void=True)
                # Change case record status from pending
                OVCCaseRecord.objects.filter(
                    person_id=person_id, is_void=False,
                    case_record_id=case_record_id,
                    case_stage=0).update(case_stage=1)
            except Exception as e:
                print('Case stage update error - %s' % (str(e)))
                pass

            # Save New
            placement_id = new_guid_32()
            OVCPlacement(
                placement_id=placement_id,
                residential_institution_id=residential_institution_name,
                residential_institution_name=residential_institution_name,
                admission_number=admission_number,
                admission_date=admission_date,
                admission_type=admission_type,
                transfer_from=transfer_from,
                transfer_from_institution_id=transfer_from,
                admission_reason=admission_reason,
                holding_period=holding_period,
                has_court_committal_order=has_court_committal_order,
                court_order_number=court_order_number,
                court_order_issue_date=court_order_issue_date,
                committing_court=committing_court,
                committing_period=committing_period,
                committing_period_units=committing_period_units,
                ob_number=ob_number,
                free_for_adoption=free_for_adoption,
                case_record_id=case_record_id,
                placement_notes=placement_notes,
                placement_type=placement_type,
                created_by=int(app_user.id),
                person_id=reg_person_pk
            ).save()

            # FormsLog
            placement_pk = placement_id
            FormsLog(
                form_id=placement_id,
                form_type_id='FTRI',
                timestamp_created=now,
                person=RegPerson.objects.get(pk=int(reg_person_pk))).save()

        else:
            print('Not POST')
    except Exception as e:
        msg = 'Residential Placement Save Error: %s' % str(e)
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))

    # Init data
    formslog = FormsLog.objects.get(form_id=placement_pk)
    init_data = RegPerson.objects.get(pk=formslog.person_id)
    msg = 'Residential Placement (%s %s) Save Succesfull' % (
        init_data.first_name, init_data.surname)
    messages.add_message(request, messages.INFO, msg)
    return HttpResponseRedirect(reverse(forms_registry))


@login_required
def view_placement(request, id):
    try:
        f = FormsLog.objects.get(form_id=id)
        person_id = int(f.person_id)
        init_data = RegPerson.objects.filter(pk=person_id)
        resultset = OVCPlacement.objects.get(placement_id=id)
        pid = str(resultset.placement_id).replace('-', '')
        org_id = int(resultset.residential_institution_name)
        user = AppUser.objects.get(id=resultset.created_by)
        organization = RegOrgUnit.objects.get(id=org_id)
        print('PID', resultset.pk, resultset.person_id)

        check_fields = ['institution_type_id',
                        'admission_type_id',
                        'admission_reason_id',
                        'yesno_id', 'period_id',
                        'sex_id', 'discharge_type_id',
                        'adverse_event_id']
        vals = get_dict(field_name=check_fields)
        com_period = resultset.committing_period
        com_units = resultset.committing_period_units
        com_date = resultset.court_order_issue_date
        com_hold = resultset.holding_period
        com_adm = resultset.admission_date
        # Get exit date
        try:
            exit_date, discharge_type, discharge_to = None, None, None
            exits = OVCDischargeFollowUp.objects.filter(
                placement_id_id=id).order_by('timestamp_created')
            for exit in exits:
                exit_date = exit.date_of_discharge
                discharge_type = exit.type_of_discharge
                discharge_to = exit.discharge_destination
                print('DIST', discharge_to, exit.created_by)
        except Exception:
            pass
        to_org_name = None
        if discharge_to:
            to_org = RegOrgUnit.objects.get(id=int(discharge_to))
            to_org_name = to_org.org_unit_name
        # Get exist date
        if com_hold:
            start_date = com_adm
            units = 'CPDA'
            period = com_hold
        else:
            start_date = com_date
            units = str(com_units)
            period = com_period
        days, ck = get_exit(period, units, start_date, exit_date)
        stay = get_stay(com_adm, exit_date)
        exits = '%s %s' % (days, ck)
        # print 'vals ---------- %s' % vals
    except Exception as e:
        msg = 'Residential Placement View Error: %s' % str(e)
        messages.add_message(request, messages.ERROR, msg)
        redirect_url = reverse(forms_registry)
        return HttpResponseRedirect(redirect_url)
    return render(request,
                  'forms/view_placement.html',
                  {'init_data': init_data, 'placement_id': pid,
                   'vals': vals, 'user': user, 'exit_date': exit_date,
                   'org_unit': organization.org_unit_name,
                   'resultset': resultset, 'exit': exits,
                   'exit_period': stay, 'discharge': discharge_type,
                   'transfer_to': to_org_name, 'transfer_to_id': discharge_to})


@login_required
def edit_placement(request, id):
    try:
        if request.method == 'POST':
            # child_firstname = request.POST.get('child_firstname')
            # child_lastname = request.POST.get('child_lastname')
            # child_surname = request.POST.get('child_surname')
            # child_gender = request.POST.get('child_gender')
            # child_dob = request.POST.get('child_dob')
            # residential_institution_type = request.POST.get('residential_institution_type')
            residential_institution_name = request.POST.get(
                'residential_institution_name')
            admission_date = request.POST.get('admission_date')
            admission_number = request.POST.get('admission_number')
            transfer_from = request.POST.get(
                'transfer_from') if request.POST.get('transfer_from') else None
            admission_type = request.POST.get('admission_type')
            admission_reason = request.POST.get('admission_reason')
            has_court_committal_order = request.POST.get(
                'has_court_committal_order')
            holding_period = request.POST.get(
                'holding_period') if request.POST.get('holding_period') else None
            court_order_number = request.POST.get(
                'court_order_number') if request.POST.get('court_order_number') else None
            court_order_issue_date = request.POST.get(
                'court_order_issue_date') if request.POST.get('court_order_issue_date') else None
            committing_court = request.POST.get(
                'committing_court') if request.POST.get('committing_court') else None
            committing_period = request.POST.get(
                'committing_period') if request.POST.get('committing_period') else None
            committing_period_units = request.POST.get(
                'committing_period_units') if request.POST.get('committing_period_units') else None
            ob_number = request.POST.get(
                'ob_number') if request.POST.get('ob_number') else None
            free_for_adoption = request.POST.get('free_for_adoption')
            workforce_member_plcmnt = request.POST.get(
                'workforce_member_plcmnt')
            placement_notes = request.POST.get('placement_notes')
            placement_type = request.POST.get('placement_type')
            person_id = request.POST.get('person_id')
            now = timezone.now()

            # Convert dates
            if admission_date:
                admission_date = convert_date(admission_date)
            else:
                admission_date = None

            if court_order_issue_date:
                court_order_issue_date = convert_date(court_order_issue_date)
            else:
                court_order_issue_date = None

            """
            # Update RegPerson
            person = RegPerson.objects.get(pk=person_id)
            person.first_name = child_firstname
            person.other_names = child_lastname
            person.surname = child_surname
            person.sex_id = child_gender
            person.date_of_birth = child_dob
            person.save(update_fields=['first_name',
                                       'other_names',
                                       'surname',
                                       'sex_id',
                                       'date_of_birth'])
            """

            # Update OVCPlacement
            ovcplacement = OVCPlacement.objects.get(placement_id=id)
            ovcplacement.residential_institution_name = residential_institution_name
            ovcplacement.residential_institution_id = int(residential_institution_name)
            ovcplacement.admission_date = admission_date
            ovcplacement.admission_type = admission_type
            ovcplacement.transfer_from = transfer_from
            ovcplacement.admission_reason = admission_reason
            ovcplacement.admission_number = admission_number
            ovcplacement.holding_period = holding_period

            ovcplacement.has_court_committal_order = has_court_committal_order
            if has_court_committal_order == 'AYES':
                ovcplacement.court_order_number = court_order_number
                ovcplacement.court_order_issue_date = court_order_issue_date
                ovcplacement.committing_court = committing_court
                ovcplacement.committing_period = committing_period
                ovcplacement.committing_period_units = committing_period_units
            else:
                ovcplacement.ob_number = ob_number

            if placement_type == 'Normal':
                ovcplacement.free_for_adoption = free_for_adoption

            ovcplacement.placement_notes = placement_notes
            ovcplacement.save(update_fields=['residential_institution_name',
                                             'admission_date',
                                             'admission_type',
                                             'transfer_from',
                                             'admission_reason',
                                             'admission_number',
                                             'holding_period',
                                             'has_court_committal_order',
                                             'court_order_number',
                                             'court_order_issue_date',
                                             'committing_court',
                                             'committing_period',
                                             'committing_period_units',
                                             'ob_number',
                                             'free_for_adoption',
                                             'placement_notes'])

            params = {}
            params['transaction_type_id'] = 'UPDU'
            params['interface_id'] = 'INTW'
            params['form_id'] = id
            save_audit_trail(request, params, 'FTRI')

            # Init data
            formslog = FormsLog.objects.get(form_id=id)
            init_data = RegPerson.objects.get(pk=formslog.person_id)
            msg = 'Residential Placement (%s %s) Update Succesfull' % (
                init_data.first_name, init_data.surname)

            messages.add_message(request, messages.INFO, msg)
            redirect_url = reverse(forms_registry)
            return HttpResponseRedirect(redirect_url)

    except Exception as e:
        msg = 'Residential Placement Edit Error: %s' % str(e)
        messages.add_message(request, messages.ERROR, msg)
        redirect_url = reverse(forms_registry)
        return HttpResponseRedirect(redirect_url)

    # Get app_user
    username = request.user.get_username()
    app_user = AppUser.objects.get(username=username)
    user_id = app_user.id

    # Get Person/Child Data
    f = FormsLog.objects.get(form_id=id)
    person_id = int(f.person_id)
    init_data = RegPerson.objects.filter(pk=person_id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)

    # Get Placement Data
    ovcplacement = OVCPlacement.objects.get(placement_id=id)
    pid = str(ovcplacement.placement_id)

    court_order_issue_date = ovcplacement.court_order_issue_date
    if court_order_issue_date:
        court_order_issue_date = court_order_issue_date.strftime('%d-%b-%Y')

    print('placement institution ... %s' % ovcplacement.residential_institution_name)
    print('period', ovcplacement.committing_period_units)
    try:
        inst_id = int(ovcplacement.residential_institution_name)
    except Exception as e:
        print('Could not get institution id - %s' % str(e))
        inst_id = 0

    form = ResidentialForm({
        'person_id': person_id,
        'user_id': user_id,
        'admission_number': ovcplacement.admission_number,
        # Placement Type
        'placement_type': ovcplacement.placement_type,

        # Admission Data
        'residential_institution_name': inst_id,
        'admission_type': ovcplacement.admission_type,
        'transfer_from': ovcplacement.transfer_from,
        'admission_date': (ovcplacement.admission_date).strftime('%d-%b-%Y'),
        'admission_reason': ovcplacement.admission_reason,

        # Placement Data
        'holding_period': ovcplacement.holding_period,
        'has_court_committal_order': ovcplacement.has_court_committal_order,
        'court_order_number': ovcplacement.court_order_number,
        'court_order_issue_date': court_order_issue_date,
        'committing_court': ovcplacement.committing_court,
        'ob_number': ovcplacement.ob_number,
        'free_for_adoption': ovcplacement.free_for_adoption,
        'placement_notes': ovcplacement.placement_notes,
        'committing_period_units': ovcplacement.committing_period_units.strip(),
        'committing_period': ovcplacement.committing_period
    })
    return render(request,
                  'forms/edit_placement.html',
                  {'form': form, 'placement_id': pid,
                   'vals': vals, 'inst_id': inst_id,
                   'init_data': init_data})


def delete_placement(request):
    now = timezone.now()

    try:
        if request.method == 'POST':
            case_event_id = request.POST.get('event_id')

            # Update OVCCaseEvents
            ovc_ce = OVCCaseEvents.objects.get(pk=case_event_id)
            ovc_ce.is_void = True
            ovc_ce.save(update_fields=['is_void'])

            # Delete/Void Residential Placement
            ovc_plcmnts = OVCPlacement.objects.filter(
                case_event_id=case_event_id)
            for ovc_plcmnt in ovc_plcmnts:
                ovc_plcmnt.is_void = True
                ovc_plcmnt.save(update_fields=['is_void'])
        else:
            print('Not POST')
    except Exception as e:
        print('Court Orders Delete Error: %s' % str(e))
    # return HttpResponseRedirect(reverse(ovc_search))
    return HttpResponse('Court Orders Deleted')


def manage_placementfollowup(request):
    try:
        if request.method == 'POST':
            person = request.POST.get('person')
            jsonPlacementEventsData = []
            placement_id = None
            placements = OVCPlacement.objects.filter(
                person_id=int(person), is_active=True)
            for placement in placements:
                placement_id = placement.placement_id

            # ITP/Tracing/Case Conferencing/Home Visit
            followup1_data = OVCPlacementFollowUp.objects.filter(
                person_id=person, placement_id_id=placement_id,
                is_void=False).order_by('-timestamp_created')
            if followup1_data:
                for followup1data in followup1_data:
                    followup_type = None
                    if followup1data.followup_type == 'FUIT':
                        followup_type = 'Individual Treatment Plan'
                    elif followup1data.followup_type == 'FUCC':
                        followup_type = 'Case Conferencing'
                    elif followup1data.followup_type == 'FHEA':
                        followup_type = 'Home Visit'
                    elif followup1data.followup_type == 'FUTT':
                        followup_type = 'Tracing'
                    elif followup1data.followup_type == 'FUIC':
                        followup_type = 'Individual Care Plan'
                    elif followup1data.followup_type == 'FUAP':
                        followup_type = 'Assessment and Placement'
                    elif followup1data.followup_type == 'FFOC':
                        followup_type = 'Foster Care'
                    elif followup1data.followup_type == 'FUSP':
                        followup_type = 'Service'

                    jsonPlacementEventsData.append({
                        'pk': followup1data.placememt_followup_id,
                        'person_id': followup1data.person_id,
                        'followup_type': followup_type,
                        'followup_date': (followup1data.followup_date).strftime('%d-%b-%Y'),
                        'followup_details': followup1data.followup_details,
                        'followup_outcome': followup1data.followup_outcome
                    })
            # Education
            followup2_data = OVCEducationFollowUp.objects.filter(
                person_id=person, placement_id_id=placement_id,
                is_void=False).order_by('-timestamp_created')
            if followup2_data:
                for followup2data in followup2_data:
                    followup_type = 'Education'
                    followup_outcome = 'Admitted : ' + \
                        translate(followup2data.admitted_to_school)
                    # followup_details = followup2data.education_comments if
                    # followup2data.education_comments else 'No details available'

                    edulevels = []
                    if(followup2data.admitted_to_school == 'AYES'):
                        ovc_edulevels = OVCEducationLevelFollowUp.objects.filter(
                            education_followup_id=followup2data.education_followup_id, is_void=False)
                        for ovc_edulevel in ovc_edulevels:
                            edulevels.append(
                                str(translate(ovc_edulevel.admission_level)))
                        str_edulevels = ','.join(edulevels)
                        followup_details = 'Admitted on ' + (followup2data.admission_to_school_date).strftime(
                            '%d-%b-%Y') + ' at level(s) ' + str_edulevels
                        followup_date = (
                            followup2data.admission_to_school_date).strftime('%d-%b-%Y')
                    else:
                        followup_details = 'No details available to display'
                        followup_date = 'Missing date of admission'

                    jsonPlacementEventsData.append({
                        'pk': followup2data.education_followup_id,
                        'person_id': followup2data.person_id,
                        'followup_type': followup_type,
                        'followup_date': followup_date,
                        'followup_details': followup_details,
                        'followup_outcome': followup_outcome
                    })
            # Court
            """ Get CaseRecordSheet case_ids """
            case_ids = []
            ovc_caserecords = OVCCaseRecord.objects.filter(
                person_id=person, is_void=False).order_by('-timestamp_created')
            if ovc_caserecords:
                for ovc_caserecord in ovc_caserecords:
                    case_ids.append(str(ovc_caserecord.case_id))

            """ Get CaseEvents case_event_ids """
            case_event_ids = []
            ovc_caseevents = OVCCaseEvents.objects.filter(
                case_id__in=case_ids, placement_id_id=placement_id, is_void=False)
            if ovc_caseevents:
                for ovc_caseevent in ovc_caseevents:
                    case_event_ids.append(str(ovc_caseevent.case_event_id))

                followup_type = 'Court'
                followup3_data = ovc_caseevents
                for followup3data in followup3_data:
                    followup_outcome = ''
                    """ Get Court Data For CourtOutcome=Ruling) """
                    ovc_courtsessions = OVCCaseEventCourt.objects.filter(
                        case_event_id=followup3data.case_event_id,
                        is_void=False).order_by('-timestamp_created')
                    if(ovc_courtsessions):
                        courtorders = []
                        for ovc_courtsession in ovc_courtsessions:
                            if ovc_courtsession.court_order:
                                courtorders.append(
                                    translate(ovc_courtsession.court_order))
                        if courtorders:
                            followup_outcome = ','.join(courtorders)
                        else:
                            """ Get Court Data For Court Session Types Mention) """
                            if followup3data.next_hearing_date:
                                followup_outcome = 'Adjournment, next hearing date is ' + \
                                    (followup3data.next_hearing_date).strftime(
                                        '%d-%b-%Y')
                            if followup3data.next_mention_date:
                                followup_outcome = 'Mention, next mention date is ' + \
                                    (followup3data.next_mention_date).strftime(
                                        '%d-%b-%Y')
                            if followup3data.plea_taken:
                                followup_outcome = 'Plea taken(%s), next mention date is %s' % (translate(
                                    followup3data.plea_taken), (followup3data.next_mention_date).strftime('%d-%b-%Y'))

                        followup_type = (
                            followup3data.case_event_type_id).title()
                        jsonPlacementEventsData.append({
                            'pk': followup3data.case_event_id,
                            'person_id': person,
                            'followup_type': followup_type,
                            'followup_date': (followup3data.date_of_event).strftime('%d-%b-%Y'),
                            'followup_details': followup3data.case_event_notes,
                            'followup_outcome': followup_outcome
                        })

            # Adverse Events
            ovc_adverseevents = OVCAdverseEventsFollowUp.objects.filter(
                person_id=person, placement_id_id=placement_id,
                is_void=False).order_by('-timestamp_created')
            if ovc_adverseevents:
                followup_type = 'Adverse Events'
                followup4_data = ovc_adverseevents
                followup_details = 'No details available to display'
                for followup4data in followup4_data:
                    ovc_adverseotherevents = OVCAdverseEventsOtherFollowUp.objects.filter(
                        adverse_condition_id=followup4data.adverse_condition_id, is_void=False)

                    if ovc_adverseotherevents:
                        followupdetails = []
                        for ovc_adverseotherevent in ovc_adverseotherevents:
                            followupdetails.append(
                                translate(ovc_adverseotherevent.adverse_condition))
                        followup_details = ','.join(followupdetails)

                    jsonPlacementEventsData.append({
                        'pk': followup4data.adverse_condition_id,
                        'person_id': person,
                        'followup_type': followup_type,
                        'followup_date': (followup4data.adverse_event_date).strftime('%d-%b-%Y'),
                        'followup_details': followup_details,
                        'followup_outcome': translate(followup4data.adverse_condition_description)
                    })
            # Discharge
            followup5_data = OVCDischargeFollowUp.objects.filter(
                person_id=person, placement_id_id=placement_id,
                is_void=False).order_by('-timestamp_created')
            if followup5_data:
                followup_type = 'Discharge'
                for followup5data in followup5_data:
                    jsonPlacementEventsData.append({
                        'pk': followup5data.discharge_followup_id,
                        'person_id': person,
                        'followup_type': followup_type,
                        'followup_date': (followup5data.timestamp_created).strftime('%d-%b-%Y'),
                        'followup_details': followup5data.reason_of_discharge,
                        'followup_outcome': translate(followup5data.type_of_discharge)
                    })

    except Exception as e:
        print('Load ResidentialPlacementFollowup Events Error -  %s' % str(e))
    return JsonResponse(jsonPlacementEventsData,
                        content_type='application/json',
                        safe=False)

#------------------------- School & Bursary --------------------------#


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def background_details(request):
    try:
        if request.method == 'POST':
            resultsets = None
            person_type = None

            form = OVCSearchForm(
                data=request.POST, initial={'person_type': 'TBVC'})
            check_fields = ['sex_id']
            vals = get_dict(field_name=check_fields)

            person_type = 'TBVC'
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')
            number_of_results = 50
            type_of_person = [person_type] if person_type else []
            include_died = False

            resultsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)

            if resultsets:
                for result in resultsets:

                    # Add SchoolInfo & ClassInfo
                    class_list = []
                    schoolname_list = []
                    admission_levels = []
                    admission_sublevels = []
                    schoolname = 'Not admitted to school'

                    ovc_educationinfos = OVCEducationFollowUp.objects.filter(
                        person=int(result.id), is_void=False)
                    if ovc_educationinfos:
                        for ovc_educationinfo in ovc_educationinfos:
                            if ovc_educationinfo.school_id_id:
                                schoolname = translate_school(
                                    str(ovc_educationinfo.school_id_id))

                                # Get Levels
                                ovc_educationlevelinfo = OVCEducationLevelFollowUp.objects.get(
                                    education_followup_id=ovc_educationinfo.education_followup_id, is_void=False)
                                classform = translate(
                                    ovc_educationlevelinfo.admission_level)

                                setattr(result, 'schoolname', schoolname)
                                setattr(result, 'schooled', 'SCHOOLED')
                                setattr(result, 'classform', classform)
                            else:
                                # print 'found nothin'
                                setattr(result, 'schoolname', 'No School Info')
                                setattr(result, 'schooled', None)
                                setattr(result, 'classform', 'No Class Info')
                    else:
                        setattr(result, 'schoolname', 'No School Info')
                        setattr(result, 'schooled', None)
                        setattr(result, 'classform', 'No Class Info')

                msg = 'Showing results for (%s)' % search_string
                messages.add_message(request, messages.INFO, msg)
                return render(request, 'forms/background_details.html',
                              {'form': form,
                               'resultsets': resultsets,
                               'vals': vals,
                               'person_type': person_type})
            else:
                msg = 'No results for (%s).Name does not exist in database.' % search_string
                messages.add_message(request, messages.ERROR, msg)
    except Exception as e:
        msg = 'OVC search error - %s' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        # print 'exception'
    form = OVCSearchForm()
    return render(request, 'forms/background_details.html', {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_education_info(request, id):
    try:
        if request.method == 'POST':
            # Time
            now = timezone.now()

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            person = id
            admmitted_to_school = request.POST.get('admmitted_to_school')
            not_in_school_reason = request.POST.get(
                'not_in_school_reason') if request.POST.get('not_in_school_reason') else None
            name_of_school = request.POST.get(
                'name_of_school') if request.POST.get('name_of_school') else None
            admmission_type = request.POST.get(
                'admmission_type') if request.POST.get('admmission_type') else None
            admission_date = request.POST.get(
                'admission_date') if request.POST.get('admission_date') else None
            if admission_date:
                admission_date = convert_date(admission_date)
            admmission_class = request.POST.get(
                'admmission_class') if request.POST.get('admmission_class') else None
            admmission_subclass = request.POST.get(
                'admmission_subclass') if request.POST.get('admmission_subclass') else None
            education_comments = request.POST.get(
                'education_comments') if request.POST.get('education_comments') else None

            # Void any existing school info
            existing_ovc_edus = OVCEducationFollowUp.objects.filter(
                person=person)
            if existing_ovc_edus:
                for existing_ovc_edu in existing_ovc_edus:
                    existing_ovc_edu.is_void = True
                    existing_ovc_edu.save(update_fields=['is_void'])
            existing_ovc_edus_audit = FormsLog.objects.filter(
                person=person, form_type_id='FTCB')
            if existing_ovc_edus_audit:
                for existing_ovc_edu_audit in existing_ovc_edus_audit:
                    existing_ovc_edu_audit.is_void = True
                    existing_ovc_edu_audit.save(update_fields=['is_void'])

            school_id = SchoolList.objects.get(
                pk=name_of_school) if name_of_school else None
            # Save New
            ovc_edu = OVCEducationFollowUp(
                admitted_to_school=admmitted_to_school,
                not_in_school_reason=not_in_school_reason,
                school_id=school_id,
                school_admission_type=admmission_type,
                admission_to_school_date=admission_date,
                # admmission_class=admmission_class,
                # admmission_subclass=admmission_subclass,
                education_comments=education_comments,
                timestamp_created=now,
                created_by=int(user_id),
                person=RegPerson.objects.get(pk=int(str(person)))
            )
            ovc_edu.save()
            ovc_edu_pk = ovc_edu.pk

            if admmitted_to_school == 'AYES':
                OVCEducationLevelFollowUp(
                    admission_level=admmission_class,
                    admission_sublevel=admmission_subclass,
                    education_followup_id=OVCEducationFollowUp.objects.get(
                        pk=ovc_edu_pk),
                    timestamp_created=now).save()

            # FormsLog
            FormsLog(
                form_id=str(ovc_edu_pk).replace('-', ''),
                form_type_id='FTCB',
                timestamp_created=now,
                app_user=int(app_user.id),
                person=RegPerson.objects.get(pk=int(person))).save()

            # Init data
            init_data = RegPerson.objects.get(pk=id)
            msg = 'Education Details (%s %s) Save Succesfull' % (
                init_data.first_name, init_data.surname)
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseRedirect(reverse(forms_registry))
    except Exception as e:
        msg = 'Education Details Save Error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))

    # Get initial data
    init_data = RegPerson.objects.filter(pk=id)

    now = timezone.now()
    date_of_birth = now.date()
    date_today = now.date()
    for data in init_data:
        date_of_birth = data.date_of_birth
    age = relativedelta(
        date_today, date_of_birth).years if date_of_birth else 0

    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    form = BackgroundDetailsForm({'child_age': age})
    return render(request, 'forms/new_education_info.html', {'form': form, 'init_data': init_data, 'vals': vals})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_education_info(request, id):
    try:
        if request.method == 'POST':
            # Time
            now = timezone.now()

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            # person = id
            admmitted_to_school = request.POST.get('admmitted_to_school')
            not_in_school_reason = request.POST.get(
                'not_in_school_reason') if request.POST.get('not_in_school_reason') else None
            name_of_school = request.POST.get(
                'name_of_school') if request.POST.get('name_of_school') else None
            admmission_type = request.POST.get(
                'admmission_type') if request.POST.get('admmission_type') else None
            admission_date = request.POST.get(
                'admission_date') if request.POST.get('admission_date') else None
            if admission_date:
                admission_date = convert_date(admission_date)
            admmission_class = request.POST.get(
                'admmission_class') if request.POST.get('admmission_class') else None
            admmission_subclass = request.POST.get(
                'admmission_subclass') if request.POST.get('admmission_subclass') else None
            education_comments = request.POST.get(
                'education_comments') if request.POST.get('education_comments') else None

            school_id = SchoolList.objects.get(
                pk=name_of_school) if name_of_school else None

            ovc_education_followup = OVCEducationFollowUp.objects.get(
                pk=id, is_void=False)
            ovc_education_followup.admitted_to_school = admmitted_to_school
            ovc_education_followup.not_in_school_reason = not_in_school_reason
            ovc_education_followup.school_id = school_id
            ovc_education_followup.school_admission_type = admmission_type
            ovc_education_followup.admission_to_school_date = admission_date
            ovc_education_followup.education_comments = education_comments
            ovc_education_followup.save(update_fields=[
                'admitted_to_school',
                'not_in_school_reason',
                'school_id',
                'school_admission_type',
                'admission_to_school_date',
                'education_comments'])

            ovceducationlevelfollowup = OVCEducationLevelFollowUp.objects.filter(
                education_followup_id_id=ovc_education_followup.education_followup_id)
            if ovceducationlevelfollowup:
                for ovcedulevelfollowup in ovceducationlevelfollowup:
                    admmission_class = ovcedulevelfollowup.admission_level
                    admmission_subclass = ovcedulevelfollowup.admission_sublevel

                    ovceducationlevelfollowup.admission_level = admmission_class
                    ovceducationlevelfollowup.admission_sublevel = admmission_subclass
                    ovceducationlevelfollowup.save(update_fields=[
                        'admission_level',
                        'admission_sublevel'])

            params = {}
            params['transaction_type_id'] = 'UPDU'
            params['interface_id'] = 'INTW'
            params['form_id'] = id
            save_audit_trail(request, params, 'FTCB')

            # Init data
            formslog = FormsLog.objects.get(form_id=id)
            init_data = RegPerson.objects.get(pk=formslog.person_id)
            msg = 'Education Details (%s %s) Update Succesfull' % (
                init_data.first_name, init_data.surname)
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseRedirect(reverse(forms_registry))

    except Exception as e:
        msg = 'Education Details Update Error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))

    # Get PersonId/Init Data
    f = FormsLog.objects.get(form_id=id, is_void=False)
    person_id = int(f.person_id)
    init_data = RegPerson.objects.filter(pk=person_id, is_void=False)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)

    # OVCEducationFollowUp
    ovceducationfollowup = OVCEducationFollowUp.objects.get(
        pk=id, person_id=person_id, is_void=False)

    # OVCEducationLevelFollowUp
    ovceducationlevelfollowup = OVCEducationLevelFollowUp.objects.filter(
        education_followup_id_id=ovceducationfollowup.education_followup_id)
    admmission_class = ''
    admmission_subclass = ''
    if ovceducationlevelfollowup:
        for ovcedulevelfollowup in ovceducationlevelfollowup:
            admmission_class = ovcedulevelfollowup.admission_level
            admmission_subclass = ovcedulevelfollowup.admission_sublevel

    form = BackgroundDetailsForm(
        {
            'admmitted_to_school': ovceducationfollowup.admitted_to_school,
            'not_in_school_reason': ovceducationfollowup.not_in_school_reason,
            'name_of_school': ovceducationfollowup.school_id_id,
            'admmission_type': ovceducationfollowup.school_admission_type,
            'admission_date': ovceducationfollowup.admission_to_school_date,
            'education_comments': ovceducationfollowup.education_comments,
            'admmission_class': admmission_class,
            'admmission_subclass': admmission_subclass
        })
    return render(request,
                  'forms/edit_education_info.html',
                  {'form': form,
                   'init_data': init_data,
                   'vals': vals})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_education_info(request, id):
    try:
        # Get PersonId/Init Data
        f = FormsLog.objects.get(form_id=id, is_void=False)
        person_id = int(f.person_id)
        init_data = RegPerson.objects.filter(pk=person_id, is_void=False)

        # OVCEducationFollowUp
        ovceducationfollowup = OVCEducationFollowUp.objects.get(
            pk=id, person_id=person_id, is_void=False)

        # OVCEducationLevelFollowUp
        ovceducationlevelfollowup = OVCEducationLevelFollowUp.objects.filter(
            education_followup_id_id=ovceducationfollowup.education_followup_id)

        check_fields = [
            'yesno_id',
            'out_of_school_id',
            'school_type_id',
            'class_level_id',
            'vocational_training_id'
        ]
        vals = get_dict(field_name=check_fields)

        return render(request,
                      'forms/view_education_info.html',
                      {
                          'init_data': init_data,
                          'vals': vals,
                          'ovceducationfollowup': ovceducationfollowup,
                          'ovceducationlevelfollowup': ovceducationlevelfollowup
                      })
    except Exception as e:
        msg = 'Education Details View Error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_education_info(request, id):
    return HttpResponse('code')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_bursary_info(request):
    jsonBursaryResponse = []
    try:
        if request.method == 'POST':
            # Time
            now = timezone.now()
            msg = ''

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            # Save
            bursary_type = request.POST.get('bursary_type')
            disbursement_date = request.POST.get('disbursement_date')
            if disbursement_date:
                disbursement_date = convert_date(disbursement_date)
            term = request.POST.get('term')
            amount = request.POST.get('amount')
            year = request.POST.get('year')
            person = request.POST.get('person_id')

            bursaryexists = OVCBursary.objects.filter(
                bursary_type=bursary_type, year=year, term=term, person=person)
            if not bursaryexists:
                OVCBursary(
                    bursary_type=bursary_type,
                    disbursement_date=disbursement_date,
                    amount=amount,
                    year=year,
                    term=term,
                    timestamp_created=now,
                    created_by=int(user_id),
                    person=RegPerson.objects.get(pk=int(str(person)))).save()
                jsonBursaryResponse.append({'msg': 'Bursary save success',
                                            'status': 'Success'})

            else:
                jsonBursaryResponse.append({'msg': 'You cannot issue the same bursary type for the same child in the same period.',
                                            'status': 'Issue'})
    except Exception as e:
        msg = 'Bursary save error: (%s)' % (str(e))
        jsonBursaryResponse.append({'msg': msg,
                                    'status': 'Error'})
    return JsonResponse(jsonBursaryResponse, content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_bursary_info(request):
    try:
        jsonBursaryResponse = []
        if request.method == 'POST':
            # Time
            now = timezone.now()

            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            # Update
            bursary_type = request.POST.get('bursary_type')
            disbursement_date = request.POST.get('disbursement_date')
            if disbursement_date:
                disbursement_date = convert_date(disbursement_date)
            term = request.POST.get('term')
            amount = request.POST.get('amount')
            year = request.POST.get('year')
            bursary_id = request.POST.get('bursary_id')
            person = request.POST.get('person_id')

            ovcbursary = OVCBursary.objects.get(pk=bursary_id, is_void=False)
            ovcbursary.bursary_type = bursary_type
            ovcbursary.disbursement_date = disbursement_date
            ovcbursary.term = term
            ovcbursary.amount = amount
            ovcbursary.year = year

            bursaryexists = OVCBursary.objects.filter(
                bursary_type=bursary_type, year=year, term=term, person=person)
            if not bursaryexists:
                ovcbursary.save(update_fields=['bursary_type',
                                               'disbursement_date',
                                               'term',
                                               'amount',
                                               'year'])
                jsonBursaryResponse.append({'msg': 'Bursary update success',
                                            'status': 'Success'})
            else:
                jsonBursaryResponse.append({'msg': 'You cannot issue the same bursary type for the same child in the same period.',
                                            'status': 'Issue'})
    except Exception as e:
        msg = 'Bursary update error: (%s)' % (str(e))
        jsonBursaryResponse.append({'msg': msg,
                                    'status': 'Error'})
    return JsonResponse(jsonBursaryResponse, content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_bursary_info(request):
    try:
        if request.method == 'POST':
            bursary_id = request.POST.get('bursary_id')
            jsonBursaryData = []

            bursary_data = OVCBursary.objects.filter(
                bursary_id=bursary_id, is_void=False).order_by('-timestamp_created')

            if bursary_data:
                for bursarydata in bursary_data:
                    jsonBursaryData.append({
                        'pk': bursarydata.bursary_id,
                        'person_id': bursarydata.person_id,
                        'bursary_type': bursarydata.bursary_type,
                        'disbursement_date': (bursarydata.disbursement_date).strftime('%d-%b-%Y'),
                        'amount': bursarydata.amount,
                        'year': bursarydata.year,
                        'term': bursarydata.term
                    })

    except Exception as e:
        print('Load Bursary Information Error: %s' % str(e))
    return JsonResponse(jsonBursaryData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_bursary_info(request):
    try:
        if request.method == 'POST':
            bursary_id = request.POST.get('bursary_id')
            print('bursary_id >> %s' % bursary_id)
            ovcbursary = OVCBursary.objects.get(pk=bursary_id, is_void=False)
            ovcbursary.is_void = True
            ovcbursary.save(update_fields=['is_void'])

            msg = 'Bursary Details Delete Successful'
            return HttpResponse(msg)
    except Exception as e:
        msg = 'Bursary Details Delete Error: (%s)' % (str(e))
        return HttpResponse(msg)
    return HttpResponse('Delete Bursary Info')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_school(request):
    try:
        if request.method == 'POST':
            # Get app_user
            username = request.user.get_username()
            app_user = AppUser.objects.get(username=username)
            user_id = app_user.id

            school_name = request.POST.get('school_name')
            type_of_school = request.POST.get('type_of_school')
            school_subcounty = request.POST.get('school_subcounty')
            school_ward = request.POST.get('school_ward')

            # print 'new_school_params >>  school_name(%s), type_of_school(%s),
            # school_subcounty(%s), school_ward(%s)' %(school_name,
            # type_of_school, school_subcounty, school_ward)

            SchoolList(
                school_name=school_name.title(),
                type_of_school=type_of_school,
                school_subcounty=SetupGeography.objects.get(
                    pk=int(school_subcounty)),
                school_ward=SetupGeography.objects.get(pk=int(school_ward)),
                created_by=user_id
            ).save()

            msg = 'School saved successfully.'
            messages.add_message(request, messages.INFO, msg)
            redirect_url = reverse(background_details)
            return HttpResponseRedirect(redirect_url)
    except Exception as e:
        print('An error occured while saving - %s' % str(e))
        msg = 'Error saving School.'
        messages.add_message(request, messages.ERROR, msg)
        redirect_url = reverse(background_details)
        return HttpResponseRedirect(redirect_url)
    form = OVCSchoolForm()
    return render(request, 'forms/new_school.html', {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def bursary_followup(request, id):
    # Get initial data
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    eduinfos = OVCEducationFollowUp.objects.filter(person_id=id, is_void=False)

    form = OVCBursaryForm({'person_id': id})

    try:
        if eduinfos:
            for eduinfo in eduinfos:
                admitted_to_school = eduinfo.admitted_to_school
                if admitted_to_school == 'AYES':
                    return render(request,
                                  'forms/bursary_followup.html',
                                  {'form': form,
                                   'init_data': init_data,
                                   'eduinfo': eduinfo,
                                   'vals': vals})
                else:
                    msg = 'This child school information exists, but he is not admitted to any school!'
                    messages.add_message(request, messages.ERROR, msg)
                    redirect_url = reverse(forms_registry)
                    return HttpResponseRedirect(redirect_url)
        else:
            msg = 'School information is missing - Please fill.'
            messages.add_message(request, messages.ERROR, msg)
            redirect_url = reverse(forms_registry)
            return HttpResponseRedirect(redirect_url)
    except Exception as e:
        raise e
    else:
        pass
    finally:
        pass


# -------------------- OVC Care ------------------------------------------#
# -------------------- OVC Care ------------------------------------------#
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def csi(request):
    form = OVCCareSearchForm(
        data=request.POST, initial={'person_type': 'TBVC'})
    if request.method == 'POST':
        resultsets = None
        person_type = None

        try:
            form = OVCCareSearchForm(data=request.POST, initial={
                'person_type': 'TBVC'})
            check_fields = ['sex_id',
                            'person_type_id',
                            'identifier_type_id']
            vals = get_dict(field_name=check_fields)

            person_type = 'TBVC'
            search_string = request.POST.get('search_name')
            search_criteria = request.POST.get('search_criteria')
            number_of_results = 50
            type_of_person = [person_type] if person_type else []
            include_died = False

            resultsets = get_list_of_persons(
                search_string=search_string,
                number_of_results=number_of_results,
                in_person_types=type_of_person,
                include_died=include_died,
                search_criteria=search_criteria)

            if resultsets:
                for result in resultsets:

                    # Add case_count to result <object>
                    case_count = OVCCaseRecord.objects.filter(
                        person=int(result.id), is_void=False).count()
                    setattr(result, 'case_count', case_count)

                    # Add child_geo to result <object>
                    ovc_persongeos = RegPersonsGeo.objects.filter(person=int(
                        result.id)).values_list('area_id', flat=True).order_by('area_id')
                    geo_locs = []
                    for ovc_persongeo in ovc_persongeos:
                        area_id = str(ovc_persongeo)
                        geo_locs.append(translate_geo(int(area_id)))

                    persongeos = ', '.join(geo_locs)

                    setattr(result, 'ovc_persongeos', persongeos)

                msg = 'Showing results for (%s)' % search_string
                messages.add_message(request, messages.INFO, msg)
                return render(request, 'forms/csi.html',
                              {'form': form,
                               'resultsets': resultsets,
                               'vals': vals,
                               'person_type': person_type})
            else:
                msg = 'No results for (%s).Name does not exist in database.' % search_string
                messages.add_message(request, messages.ERROR, msg)
        except Exception as e:
            msg = 'OVC search error - %s' % (str(e))
            messages.add_message(request, messages.INFO, msg)
        return HttpResponseRedirect(reverse(ovc_registry))
    else:
        form = OVCCareSearchForm()
        return render(request, 'forms/csi.html',
                      {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_csi(request, id):
    try:
        if request.method == 'POST':
            event_type_id = 'FCSI'
            date_of_csi = request.POST.get('date_of_csi')
            if date_of_csi:
                date_of_csi = convert_date(date_of_csi)

            """ Save CSIEvent """
            event_counter = OVCCareEvents.objects.filter(
                event_type_id=event_type_id, person=id, is_void=False).count()
            ovccareevent = OVCCareEvents(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                date_of_event=date_of_csi,
                created_by=request.user.id,
                person=RegPerson.objects.get(pk=int(id))
            )
            ovccareevent.save()
            new_pk = ovccareevent.pk

            # Domain Evaluation
            food_security = request.POST.get('food_security')  # HNU1
            nutrition_growth = request.POST.get('nutrition_growth')  # HNU2
            wellness = request.POST.get('wellness')  # HNU3
            healthcare_services = request.POST.get(
                'healthcare_services')  # HNU4
            shelter = request.POST.get('shelter')  # SHC1
            care = request.POST.get('care')  # SHC2
            abuse_exploitation = request.POST.get('abuse_exploitation')  # PRO1
            legal_protection = request.POST.get('legal_protection')  # PRO2
            emotional_health = request.POST.get('emotional_health')  # PSS1
            social_behaviour = request.POST.get('social_behaviour')  # PSS2
            perfomance = request.POST.get('perfomance')  # EDU1
            education_work = request.POST.get('education_work')  # EDU2
            household_strengthening = request.POST.get(
                'household_strengthening')  # HES1

            my_kvals = []
            my_kvals.append({"entity": "HNU1", "value": food_security})
            my_kvals.append({"entity": "HNU2", "value": nutrition_growth})
            my_kvals.append({"entity": "HNU3", "value": wellness})
            my_kvals.append({"entity": "HNU4", "value": healthcare_services})
            my_kvals.append({"entity": "SHC1", "value": shelter})
            my_kvals.append({"entity": "SHC2", "value": care})
            my_kvals.append({"entity": "PRO1", "value": abuse_exploitation})
            my_kvals.append({"entity": "PRO2", "value": legal_protection})
            my_kvals.append({"entity": "PSS1", "value": emotional_health})
            my_kvals.append({"entity": "PSS2", "value": social_behaviour})
            my_kvals.append({"entity": "EDU1", "value": perfomance})
            my_kvals.append({"entity": "EDU2", "value": education_work})
            my_kvals.append({"entity": "HES1", "value": household_strengthening})
            for kvals in my_kvals:
                key = kvals["entity"]
                value = kvals["value"]
                attribute = "FCSI"
                OVCCareEAV(
                    entity=key,
                    attribute=attribute,
                    value=value,
                    event=OVCCareEvents.objects.get(pk=new_pk)
                ).save()

            # CSI Priorities
            olmis_priority_service_provided_list = request.POST.get(
                'olmis_priority_service_provided_list')
            olmis_priority_data = json.loads(olmis_priority_service_provided_list)
            for priority_data in olmis_priority_data:
                service_grouping_id = new_guid_32()
                olmis_priority_domain = priority_data['olmis_priority_domain']
                olmis_priority_service = priority_data['olmis_priority_service']
                services = olmis_priority_service.split(',')
                for service in services:
                    OVCCarePriority(
                        domain=olmis_priority_domain,
                        service=service,
                        event=OVCCareEvents.objects.get(pk=new_pk),
                        service_grouping_id=service_grouping_id
                    ).save()

            # Support/Services
            olmis_service_provided_list = request.POST.get(
                'olmis_service_provided_list')
            olmis_service_data = json.loads(olmis_service_provided_list)
            for service_data in olmis_service_data:
                service_grouping_id = new_guid_32()
                olmis_domain = service_data['olmis_domain']
                olmis_service = service_data['olmis_service']
                olmis_service_date = service_data['olmis_service_date']
                if olmis_service_date:
                    olmis_service_date = convert_date(olmis_service_date)
                olmis_service_provider = service_data['olmis_service_provider']
                olmis_place_of_service = service_data['olmis_place_of_service']
                OVCCareServices(
                    service_provided=olmis_service,
                    service_provider=olmis_service_provider,
                    place_of_service=olmis_place_of_service,
                    date_of_encounter_event=olmis_service_date,
                    event=OVCCareEvents.objects.get(pk=new_pk),
                    service_grouping_id=service_grouping_id
                ).save()

            msg = 'CSI Needs Assessment Save Successful'
            messages.add_message(request, messages.INFO, msg)
            url = reverse('ovc_view', kwargs={'id': id})
            # return HttpResponseRedirect(reverse(forms_registry))
            return HttpResponseRedirect(url)
    except Exception as e:
        msg = 'CSI Needs Assessment save error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    form = OVCCsiForm()
    return render(request,
                  'forms/new_csi.html',
                  {'form': form,
                   'init_data': init_data,
                   'vals': vals,
                   'person': id})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_csi(request, id):
    try:
        if request.method == 'POST':
            form = OVCCsiForm(data=request.POST)

            date_of_csi = request.POST.get('date_of_csi')
            if date_of_csi:
                date_of_csi = convert_date(date_of_csi)

            """ Update CSIEvent """
            ovccareevent = OVCCareEvents.objects.get(event=id, is_void=False)
            ovccareevent.date_of_event = date_of_csi
            ovccareevent.save(update_fields=['date_of_event'])

            # Domain Evaluation
            food_security = request.POST.get('food_security')  # HNU1
            nutrition_growth = request.POST.get('nutrition_growth')  # HNU2
            wellness = request.POST.get('wellness')  # HNU3
            healthcare_services = request.POST.get(
                'healthcare_services')  # HNU4
            shelter = request.POST.get('shelter')  # SHC1
            care = request.POST.get('care')  # SHC2
            abuse_exploitation = request.POST.get('abuse_exploitation')  # PRO1
            legal_protection = request.POST.get('legal_protection')  # PRO2
            emotional_health = request.POST.get('emotional_health')  # PSS1
            social_behaviour = request.POST.get('social_behaviour')  # PSS2
            perfomance = request.POST.get('perfomance')  # EDU1
            education_work = request.POST.get('education_work')  # EDU2
            household_strengthening = request.POST.get(
                'household_strengthening')  # HES1
            my_kvals = []
            my_kvals.append({"entity": "HNU1", "value": food_security})
            my_kvals.append({"entity": "HNU2", "value": nutrition_growth})
            my_kvals.append({"entity": "HNU3", "value": wellness})
            my_kvals.append({"entity": "HNU4", "value": healthcare_services})
            my_kvals.append({"entity": "SHC1", "value": shelter})
            my_kvals.append({"entity": "SHC2", "value": care})
            my_kvals.append({"entity": "PRO1", "value": abuse_exploitation})
            my_kvals.append({"entity": "PRO2", "value": legal_protection})
            my_kvals.append({"entity": "PSS1", "value": emotional_health})
            my_kvals.append({"entity": "PSS2", "value": social_behaviour})
            my_kvals.append({"entity": "EDU1", "value": perfomance})
            my_kvals.append({"entity": "EDU2", "value": education_work})
            my_kvals.append({"entity": "HES1", "value": household_strengthening})
            for kvals in my_kvals:
                key = kvals["entity"]
                value = kvals["value"]
                attribute = "FCSI"
                ovccareeavs = OVCCareEAV.objects.filter(event=id, entity=key, is_void=False)
                for ovccareeav in ovccareeavs:
                    if ovccareeav.value != value:
                        ovccareeav.value = value
                        ovccareeav.save(update_fields=['value'])

            # CSI Priorities
            olmis_priority_service_provided_list = request.POST.get('olmis_priority_service_provided_list')
            new_prioritys = []
            existing_prioritys = []
            if olmis_priority_service_provided_list:
                """ Get Existing Priorities """
                existingprioritys = OVCCarePriority.objects.filter(event=id, is_void=False)
                for existingpriority in existingprioritys:
                    existing_prioritys.append({
                        'domain': str(existingpriority.domain),
                        'service': str(existingpriority.service),
                        'service_grouping_id': str(existingpriority.service_grouping_id)
                    })

                olmis_priority_data = json.loads(olmis_priority_service_provided_list)
                for priority_data in olmis_priority_data:
                    print('olmis_priority_data : %s' % olmis_priority_data)
                    if priority_data:
                        olmis_priority_service_grouping_id = priority_data['olmis_service_grouping_id']
                        olmis_priority_domain = priority_data['olmis_priority_domain']
                        olmis_priority_service = priority_data['olmis_priority_service']
                        olmis_priority_service_status = priority_data['olmis_priority_service_status']
                        services = olmis_priority_service.split(',')

                        ### New
                        if (olmis_priority_service_status == 'new'):
                            service_grouping_id = new_guid_32()
                            for service in services:
                                ovccarepriority = OVCCarePriority(
                                    domain=olmis_priority_domain,
                                    service=service,
                                    event=OVCCareEvents.objects.get(pk=id),
                                    service_grouping_id=service_grouping_id
                                ).save()
                        if olmis_priority_service:
                            new_prioritys.append({
                                'domain': olmis_priority_domain,
                                'services': olmis_priority_service,
                                'service_grouping_id': olmis_priority_service_grouping_id
                            })

                            ### Cater for removed services
                nservices = []
                nservice_grouping_ids = []
                for n_prioritys in new_prioritys:
                    ndomain = n_prioritys['domain']
                    nservice = n_prioritys['services']
                    nservice_grouping_id = n_prioritys['service_grouping_id']
                    nservice_grouping_ids.append(str(nservice_grouping_id))
                    _nservices = nservice.split(',')
                    for _nsvc in _nservices:
                        nservices.append(str(_nsvc))

                for existing_priority in existing_prioritys:
                    edomain = existing_priority['domain']
                    eservice = existing_priority['service']
                    eservice_grouping_id = existing_priority['service_grouping_id']
                    if (eservice not in nservices):
                        ### delete service
                        print('eservice (%s), service_grouping_id (%s)' % (eservice, service_grouping_id))
                        ovcexistingservices = OVCCarePriority.objects.filter(service=eservice,
                                                                             service_grouping_id=eservice_grouping_id)
                        for ovcexistingservice in ovcexistingservices:
                            ovcexistingservice.is_void = True
                            ovcexistingservice.save(update_fields=['is_void'])
            """
            # Support/Services
            olmis_service_provided_list = request.POST.get('olmis_service_provided_list')
            new_services_provided = []
            existing_services_provided = []
            if olmis_service_provided_list:
                #Get Existing Services/Support
                existingservices = OVCCareServices.objects.filter(event_id=id, is_void=False)
                for existingservice in existingservices:
                    existing_services_provided.append({
                        'olmis_domain': str(existingservice.olmis_domain),
                        'olmis_service': str(existingservice.olmis_service),
                        'olmis_service_date': existingservice.olmis_service_date,
                        'place_of_service': existingservice.place_of_service,
                        'olmis_service_date': existingservice.date_of_encounter_event,
                        'service_grouping_id': str(existingservice.service_grouping_id)
                    })
            """
            msg = 'CSI Needs Assessment Update Successful'
            messages.add_message(request, messages.INFO, msg)
            url = reverse('ovc_view', kwargs={'id': id})
            # return HttpResponseRedirect(reverse(forms_registry))
            return HttpResponseRedirect(url)
    except Exception as e:
        msg = 'CSI Needs Assessment edit error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))

    # get main data
    csi_events_data = OVCCareEvents.objects.get(event=id, is_void=False)

    # get domain evaluation data
    csi_eav_data = OVCCareEAV.objects.filter(event=id, is_void=False).values('entity', 'value').order_by('entity')
    eavdata = []
    for d in csi_eav_data:
        eavdata.append(str(d['value']))

    # get priority data
    print('EDTs', eavdata)
    csi_priority_data = OVCCarePriority.objects.filter(event=id, is_void=False)
    jsonPrData = []
    resultsetspr = []
    pr_grouping_ids = []
    for pr_data in csi_priority_data:
        pr_grouping_id = str(pr_data.service_grouping_id)
        if not pr_grouping_id in pr_grouping_ids:
            pr_grouping_ids.append(pr_grouping_id)

    pr_needs = None
    domain = None
    for pr_grouping_id in pr_grouping_ids:
        services = []
        pr_needs = csi_priority_data.filter(service_grouping_id=pr_grouping_id)
        for pr_need in pr_needs:
            services.append(str(pr_need.service))
            domain = pr_need.domain

        jsonPrData.append({
            "domain": domain,
            "service": services,
            "service_grouping_id": pr_grouping_id
        })
    print('jsonPrData : %s' % jsonPrData)
    resultsetspr.append(jsonPrData)

    # get services data
    csi_services_data = OVCCareServices.objects.filter(event=id, is_void=False)
    jsonSvcData = []
    resultsetssvc = []
    svc_grouping_ids = []
    for svc_data in csi_services_data:
        svc_grouping_id = str(svc_data.service_grouping_id)
        if not svc_grouping_id in svc_grouping_ids:
            svc_grouping_ids.append(svc_grouping_id)

    csi_services = None
    for svc_grouping_id in svc_grouping_ids:
        csi_services = csi_services_data.filter(service_grouping_id=svc_grouping_id)
        for csi_service in csi_services:
            setuplist = SetupList.objects.get(item_id=csi_service.service_provided, item_category='Service')
            field_name = setuplist.field_name
            setuplist2 = SetupList.objects.get(item_sub_category=field_name, item_category='Domain')
            domain = setuplist2.item_id

            jsonSvcData.append({
                "domain": domain,
                "service_provided": csi_service.service_provided,
                "service_provider": csi_service.service_provider,
                "place_of_service": csi_service.place_of_service,
                "date_of_encounter_event": (csi_service.date_of_encounter_event).strftime('%d-%b-%Y'),
                "service_grouping_id": str(csi_service.service_grouping_id)
            })
    resultsetssvc.append(jsonSvcData)

    print('nnnn', eavdata)
    date_of_csi = (csi_events_data.date_of_event).strftime('%d-%b-%Y')
    form = OVCCsiForm({
        # Domain Evaluation
        'perfomance': eavdata[0],
        'education_work': eavdata[1],
        'household_strengthening': eavdata[2],
        'food_security': eavdata[3],
        'nutrition_growth': eavdata[4],
        'wellness': eavdata[5],
        'healthcare_services': eavdata[6],
        'abuse_exploitation': eavdata[7],
        'legal_protection': eavdata[8],
        'emotional_health': eavdata[9],
        'social_behaviour': eavdata[10],
        'shelter': eavdata[11],
        'care': eavdata[12],
        'date_of_csi': date_of_csi
    })

    f = OVCCareEvents.objects.get(pk=id, is_void=False)
    person_id = int(f.person_id)
    init_data = RegPerson.objects.filter(pk=person_id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    return render(request,
                  'forms/edit_csi.html',
                  {'form': form,
                   'init_data': init_data,
                   'vals': vals,
                   'resultsetspr': resultsetspr,
                   'resultsetssvc': resultsetssvc})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_csi(request, id):
    f = OVCCareEvents.objects.get(pk=id, is_void=False)
    person_id = int(f.person_id)
    init_data = RegPerson.objects.filter(pk=person_id)
    check_fields = ['sex_id', 'csi_grade_id']
    vals = get_dict(field_name=check_fields)

    try:
        # get main data
        csi_events_data = OVCCareEvents.objects.get(event=id, is_void=False)

        csis = {}
        csis['HNU1'] = 'Food Security'
        csis['HNU2'] = 'Nutrition and Growth'
        csis['HNU3'] = 'Wellness'
        csis['HNU4'] = 'Healthcare Services'
        csis['SHC1'] = 'Shelter'
        csis['SHC2'] = 'Care'
        csis['PRO1'] = 'Abuse and Exploitation'
        csis['PRO2'] = 'Legal Protection'
        csis['PSS1'] = 'Emotional Health'
        csis['PSS2'] = 'Social Behavior'
        csis['EDU1'] = 'Performance'
        csis['EDU2'] = 'Education and Work'

        # get domain evaluation data
        csi_eav_data = OVCCareEAV.objects.filter(event=id, is_void=False).values('entity', 'value').order_by('entity')
        eavs, eavdata = {}, {}
        for d in csi_eav_data:
            print(d)
            eavs[str(d['entity'])] = str(d['value'])
        for csi in csis:
            eavdata[csi] = eavs[csi] if csi in eavs else None
        # get priority data
        csi_priority_data = OVCCarePriority.objects.filter(event=id, is_void=False)
        jsonPrData = []
        resultsetspr = []
        pr_grouping_ids = []
        for pr_data in csi_priority_data:
            pr_grouping_id = str(pr_data.service_grouping_id)
            if not pr_grouping_id in pr_grouping_ids:
                pr_grouping_ids.append(pr_grouping_id)

        pr_needs = None
        domain = None
        for pr_grouping_id in pr_grouping_ids:
            services = []
            pr_needs = csi_priority_data.filter(service_grouping_id=pr_grouping_id)
            for pr_need in pr_needs:
                services.append(str(pr_need.service))
                domain = pr_need.domain

            jsonPrData.append({
                "domain": domain,
                "service": services,
                "service_grouping_id": pr_grouping_id
            })
        resultsetspr.append(jsonPrData)

        # get services data
        csi_services_data = OVCCareServices.objects.filter(event=id, is_void=False)
        jsonSvcData = []
        resultsetssvc = []
        svc_grouping_ids = []
        for svc_data in csi_services_data:
            svc_grouping_id = str(svc_data.service_grouping_id)
            if not svc_grouping_id in svc_grouping_ids:
                svc_grouping_ids.append(svc_grouping_id)

        csi_services = None
        for svc_grouping_id in svc_grouping_ids:
            csi_services = csi_services_data.filter(service_grouping_id=svc_grouping_id)
            for csi_service in csi_services:
                setuplist = SetupList.objects.get(item_id=csi_service.service_provided, item_category='Service')
                field_name = setuplist.field_name
                setuplist2 = SetupList.objects.get(item_sub_category=field_name, item_category='Domain')
                domain = setuplist2.item_id

                jsonSvcData.append({
                    "domain": domain,
                    "service_provided": csi_service.service_provided,
                    "service_provider": csi_service.service_provider,
                    "place_of_service": csi_service.place_of_service,
                    "date_of_encounter_event": (csi_service.date_of_encounter_event).strftime('%d-%b-%Y'),
                    "service_grouping_id": str(csi_service.service_grouping_id)
                })
        resultsetssvc.append(jsonSvcData)

        date_of_csi = (csi_events_data.date_of_event).strftime('%d-%b-%Y')
        form = OVCCsiForm()
        print('uat', eavdata)
        return render(request,
                      'forms/view_csi.html',
                      {
                          'form': form,
                          'init_data': init_data,
                          'vals': vals,
                          'perfomance': eavdata['EDU1'],
                          'education_work': eavdata['EDU2'],
                          'household_strengthening': False,
                          'food_security': eavdata['HNU1'],
                          'nutrition_growth': eavdata['HNU2'],
                          'wellness': eavdata['HNU3'],
                          'healthcare_services': eavdata['HNU4'],
                          'abuse_exploitation': eavdata['PRO1'],
                          'legal_protection': eavdata['PRO2'],
                          'emotional_health': eavdata['PSS1'],
                          'social_behaviour': eavdata['PSS2'],
                          'shelter': eavdata['SHC1'],
                          'care': eavdata['SHC2'],
                          'date_of_csi': date_of_csi,
                          'resultsetspr': resultsetspr,
                          'resultsetssvc': resultsetssvc
                      })
    except Exception as e:
        msg = 'CSI Needs Assessment view error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    form = OVCCsiForm()
    return render(request,
                  'forms/view_csi.html',
                  {'form': 'form',
                   'init_data': init_data,
                   'vals': vals, })


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_csi(request, id):
    try:
        msg = 'CSI Needs Assessment delete successful'
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    except Exception as e:
        msg = 'CSI Needs Assessment view error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_form1b(request, id):
    if request.method == 'POST':
        save_form1b(request, id)
        msg = 'Form 1B saved successfully'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('new_form1b', kwargs={'id': id})
        return HttpResponseRedirect(url)
    deleted = request.GET.get('deleted', 0)
    if deleted:
        msg = 'Form 1B deleted successfully'
        messages.add_message(request, messages.SUCCESS, msg)
    init_data = get_ovcdetails(id)
    ovc = get_ovcdetails(id)
    cid = ovc.caretaker_id
    check_fields = ['sex_id']
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    today = datetime.now()
    month = str(today.strftime('%b'))
    f1b_allow = True if month in months else False
    vals = get_dict(field_name=check_fields)
    ffs = create_fields(['form1b_items'])
    domains = create_form_fields(ffs)
    # print ffsd
    form = OVCF1AForm(initial={'person': id, 'caretaker_id': cid})
    f1bs = OVCCareEvents.objects.filter(
        event_type_id='FM1B', person_id=cid, is_void=False)

    ev_dict = get_dict(['caregiver_critical_event_id'])

    ev_data = []
    for ovc_evt in f1bs:
        sservi, assem, ce_data = [], [], []
        event_key = str(ovc_evt.pk)
        event_date = ovc_evt.date_of_event.strftime('%d-%b-%Y')

        ovccareassems = OVCCareF1B.objects.filter(
            event=ovc_evt, is_void=False)

        for ovccareassem in ovccareassems:
            full_f1b_qn_assess = SetupList.objects.filter(
                item_id=ovccareassem.entity, item_sub_category__icontains='a')
            full_f1b_qn_servi = SetupList.objects.filter(
                item_id=ovccareassem.entity, item_sub_category__icontains='s')
            for one_f1b_qn_assess in full_f1b_qn_assess:
                assem.append({
                    # 'event_type': 'ASSESSMENTS',
                    'data': str('(' + one_f1b_qn_assess.item_id + ') ' + one_f1b_qn_assess.item_description)
                })

            for one_f1b_qn_servi in full_f1b_qn_servi:
                sservi.append({
                    # 'event_type': 'SERVICES',
                    'data': str('(' + one_f1b_qn_servi.item_id + ') ' + one_f1b_qn_servi.item_description)
                })
        # Assign CE
        cevents = OVCCareEAV.objects.filter(
            event_id=event_key, entity='CEVT', is_void=False)
        for event in cevents:
            edata = event.value
            evalue = ev_dict[edata] if edata in ev_dict else edata
            ce_data.append({'data': str('(' + edata + ') ' + evalue)})
            print('ce-data', ce_data)

        ev_data.append({
            'event_key': event_key,
            'ev_date': event_date,
            'ev_person': id,
            'services': sservi,
            'assessments': assem,
            'critical_events': ce_data,
        })

    return render(request,
                  'forms/new_form1b.html',
                  {'form': form, 'data': init_data,
                   'vals': vals, 'domains': domains, 'ovc': ovc,
                   'ev_data': ev_data,
                   #    'services': sservi, 'assessments': assem,
                   'form1b_allowed': f1b_allow, 'f1bs': f1bs})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def form1a_events(request, id):
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    form = OVCF1AForm(initial={'person': id})
    return render(request,
                  'forms/form1a_events.html',
                  {'form': form, 'init_data': init_data,
                   'vals': vals})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def save_form1a(request):
    jsonResponse = []
    try:
        if request.method == 'POST':
            # get CBO
            org_unit = None
            ou_primary = request.session.get('ou_primary')
            ou_attached = request.session.get('ou_attached')
            ou_attached = ou_attached.split(',');

            event_type_id = 'FSAM'
            args = int(request.POST.get('args'))
            person = request.POST.get('person')

            """Save Assessment"""
            if args == 1:
                date_of_assessment = request.POST.get('date_of_assessment')
                if date_of_assessment:
                    date_of_assessment = convert_date(date_of_assessment)

                # Save F1AEvent
                event_counter = OVCCareEvents.objects.filter(event_type_id=event_type_id, person=person,
                                                             is_void=False).count()
                ovccareevent = OVCCareEvents(
                    event_type_id=event_type_id,
                    event_counter=event_counter,
                    event_score=0,
                    date_of_event=date_of_assessment,
                    created_by=request.user.id,
                    person=RegPerson.objects.get(pk=int(person))
                )
                ovccareevent.save()
                new_pk = ovccareevent.pk

                # F1A Assessment
                olmis_assessment_provided_list = request.POST.get('olmis_assessment_provided_list')
                if olmis_assessment_provided_list:
                    olmis_assessment_data = json.loads(olmis_assessment_provided_list)
                    for assessment_data in olmis_assessment_data:
                        service_grouping_id = new_guid_32()
                        olmis_assessment_domain = assessment_data['olmis_assessment_domain']
                        olmis_assessment_service = assessment_data['olmis_assessment_coreservice']
                        olmis_assessment_service_status = assessment_data['olmis_assessment_coreservice_status']
                        services_status = olmis_assessment_service_status.split(',')
                        for service_status in services_status:
                            OVCCareAssessment(
                                domain=olmis_assessment_domain,
                                service=olmis_assessment_service,
                                service_status=service_status,
                                event=OVCCareEvents.objects.get(pk=new_pk),
                                service_grouping_id=service_grouping_id
                            ).save()

            if args == 2:
                date_of_cevent = request.POST.get('date_of_cevent')
                if date_of_cevent:
                    date_of_cevent = convert_date(date_of_cevent)

                # Save F1AEvent
                event_counter = OVCCareEvents.objects.filter(event_type_id=event_type_id, person=person,
                                                             is_void=False).count()
                ovccareevent = OVCCareEvents(
                    event_type_id=event_type_id,
                    event_counter=event_counter,
                    event_score=0,
                    date_of_event=date_of_cevent,
                    created_by=request.user.id,
                    person=RegPerson.objects.get(pk=int(person))
                )
                ovccareevent.save()
                new_pk = ovccareevent.pk

                # Critical Events [CEVT]
                my_kvals = []
                olmis_critical_event = request.POST.getlist('olmis_critical_event')  # DHES
                for i, cevts in enumerate(olmis_critical_event):
                    cevts = cevts.split(',')
                    for cevt in cevts:
                        my_kvals.append({"entity": "CEVT", "value": cevt})

                for kvals in my_kvals:
                    key = kvals["entity"]
                    value = kvals["value"]
                    attribute = "FSAM"
                    OVCCareEAV(
                        entity=key,
                        attribute=attribute,
                        value=value,
                        event=OVCCareEvents.objects.get(pk=new_pk)
                    ).save()

            if args == 3:
                date_of_priority = request.POST.get('date_of_priority')
                if date_of_priority:
                    date_of_priority = convert_date(date_of_priority)

                # Save F1AEvent
                event_counter = OVCCareEvents.objects.filter(event_type_id=event_type_id, person=person,
                                                             is_void=False).count()
                ovccareevent = OVCCareEvents(
                    event_type_id=event_type_id,
                    event_counter=event_counter,
                    event_score=0,
                    date_of_event=date_of_priority,
                    created_by=request.user.id,
                    person=RegPerson.objects.get(pk=int(person))
                )
                ovccareevent.save()
                new_pk = ovccareevent.pk

                # Priority Needs
                olmis_priority_service_provided_list = request.POST.get(
                    'olmis_priority_service_provided_list')
                if olmis_priority_service_provided_list:
                    olmis_priority_data = json.loads(olmis_priority_service_provided_list)
                    for priority_data in olmis_priority_data:
                        service_grouping_id = new_guid_32()
                        olmis_priority_domain = priority_data['olmis_priority_domain']
                        olmis_priority_service = priority_data['olmis_priority_service']
                        services = olmis_priority_service.split(',')
                        for service in services:
                            OVCCarePriority(
                                domain=olmis_priority_domain,
                                service=service,
                                event=OVCCareEvents.objects.get(pk=new_pk),
                                service_grouping_id=service_grouping_id
                            ).save()

            if args == 4:
                date_of_service = request.POST.get('date_of_service')
                if date_of_service:
                    date_of_service = convert_date(date_of_service)

                # Save F1AEvent
                event_counter = OVCCareEvents.objects.filter(event_type_id=event_type_id, person=person,
                                                             is_void=False).count()
                ovccareevent = OVCCareEvents(
                    event_type_id=event_type_id,
                    event_counter=event_counter,
                    event_score=0,
                    date_of_event=date_of_service,
                    created_by=request.user.id,
                    person=RegPerson.objects.get(pk=int(person))
                )
                ovccareevent.save()
                new_pk = ovccareevent.pk

                # Support/Services
                olmis_service_provided_list = request.POST.get('olmis_service_provided_list')
                if olmis_service_provided_list:
                    olmis_service_data = json.loads(olmis_service_provided_list)
                    # print 'olmis_service_data >> %s' % olmis_service_data
                    org_unit = ou_primary if ou_primary else ou_attached[0]

                    for service_data in olmis_service_data:
                        service_grouping_id = new_guid_32()
                        olmis_domain = service_data['olmis_domain']
                        olmis_service_date = service_data['olmis_service_date']
                        olmis_service_date = convert_date(olmis_service_date) if olmis_service_date != 'None' else None
                        olmis_service = service_data['olmis_service']
                        print('olmis_service: %s' % olmis_service)
                        services = olmis_service.split(',')
                        for service in services:
                            OVCCareServices(
                                domain=olmis_domain,
                                service_provided=service,
                                service_provider=org_unit,
                                # place_of_service = olmis_place_of_service,
                                date_of_encounter_event=olmis_service_date,
                                event=OVCCareEvents.objects.get(pk=new_pk),
                                service_grouping_id=service_grouping_id
                            ).save()

            msg = 'Save Successful'
            jsonResponse.append({'msg': msg})
    except Exception as e:
        msg = 'Save Error: (%s)' % (str(e))
    jsonResponse.append({'msg': msg})
    return JsonResponse(jsonResponse, content_type='application/json', safe=False)


def update_event_date(pk, date_of_assessment):
    # Save F1AEvent
    OVCCareEvents.objects.filter(pk=pk).update(date_of_event=date_of_assessment)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def update_form1a(request):
    jsonResponse = []
    try:
        if request.method == 'POST':
            # get CBO
            org_unit = None
            ou_primary = request.session.get('ou_primary')
            ou_attached = request.session.get('ou_attached')
            ou_attached = ou_attached.split(',')

            event_type_id = 'FSAM'
            args = int(request.POST.get('args'))
            person = request.POST.get('person')
            print("Step one debug")
            event_obj = OVCCareEvents.objects.get(pk=request.POST.get('event_pk'))
            """Save Assessment"""
            if args == 1:
                print("Step two debug")
                date_of_assessment = request.POST.get('date_of_assessment')
                if date_of_assessment:
                    date_of_assessment = convert_date(date_of_assessment)
                    # update_event_date(request.POST.get('event_pk'), date_of_assessment)
                # update F1AEvent

                ovc_care_assessment = OVCCareAssessment.objects.filter(event=event_obj)[:1]
                # F1A Assessment
                olmis_assessment_provided_list = request.POST.get('olmis_assessment_provided_list')
                if olmis_assessment_provided_list:

                    olmis_assessment_data = json.loads(olmis_assessment_provided_list)

                    for assessment_data in olmis_assessment_data:
                        if len(assessment_data) != 0:
                            # service_grouping_id = new_guid_32()
                            olmis_assessment_domain = assessment_data['olmis_assessment_domain']
                            olmis_assessment_service = assessment_data['olmis_assessment_coreservice']
                            olmis_assessment_service_status = assessment_data['olmis_assessment_coreservice_status']
                            services_status = olmis_assessment_service_status.split(',')
                            for service_status in services_status:
                                OVCCareAssessment(
                                    domain=olmis_assessment_domain,
                                    service=olmis_assessment_service,
                                    service_status=service_status,
                                    event=event_obj,
                                    service_grouping_id=ovc_care_assessment[0].service_grouping_id
                                ).save()
            # Critical Events
            if args == 2:
                date_of_cevent = request.POST.get('date_of_cevent')
                if date_of_cevent:
                    date_of_cevent = convert_date(date_of_cevent)

                # Critical Events [CEVT]
                my_kvals = []
                olmis_critical_event = request.POST.getlist('olmis_critical_event')  # DHES
                for i, cevts in enumerate(olmis_critical_event):
                    cevts = cevts.split(',')
                    for cevt in cevts:
                        my_kvals.append({"entity": "CEVT", "value": cevt})
                OVCCareEAV.objects.filter(event=event_obj).delete()
                for kvals in my_kvals:
                    key = kvals["entity"]
                    value = kvals["value"]
                    attribute = "FSAM"
                    OVCCareEAV(
                        entity=key,
                        attribute=attribute,
                        value=value,
                        event=event_obj
                    ).save()

            # Priority(s)
            if args == 3:
                date_of_priority = request.POST.get('date_of_priority')
                if date_of_priority:
                    date_of_priority = convert_date(date_of_priority)

                # Save F1AEvent
                event_obj = OVCCareEvents.objects.get(pk=request.POST.get('event_pk'))
                ovc_care_priority = OVCCarePriority.objects.filter(event=event_obj)[:1]
                # Priority Needs
                olmis_priority_service_provided_list = request.POST.get(
                    'olmis_priority_service_provided_list')
                if olmis_priority_service_provided_list:
                    olmis_priority_data = json.loads(olmis_priority_service_provided_list)
                    for priority_data in olmis_priority_data:
                        if len(priority_data) != 0:
                            olmis_priority_domain = priority_data['olmis_priority_domain']
                            olmis_priority_service = priority_data['olmis_priority_service']
                            services = olmis_priority_service.split(',')
                            for service in services:
                                OVCCarePriority(
                                    domain=olmis_priority_domain,
                                    service=service,
                                    event=event_obj,
                                    service_grouping_id=ovc_care_priority[0].service_grouping_id
                                ).save()
            # Services
            if args == 4:
                date_of_service = request.POST.get('date_of_service')
                if date_of_service:
                    date_of_service = convert_date(date_of_service)
                ovc_care_services = OVCCareServices.objects.filter(event=event_obj)[:1]
                # Support/Services
                olmis_service_provided_list = request.POST.get('olmis_service_provided_list')
                if olmis_service_provided_list:
                    olmis_service_data = json.loads(olmis_service_provided_list)
                    # print 'olmis_service_data >> %s' %olmis_service_data
                    org_unit = ou_primary if ou_primary else ou_attached[0]
                    print("stop point 1")
                    for service_data in olmis_service_data:
                        if service_data is not None:
                            olmis_domain = service_data['olmis_domain']
                            olmis_service_date = service_data['olmis_service_date']
                            print(olmis_service_date)
                            olmis_service_date = convert_date(
                                olmis_service_date) if olmis_service_date != 'None' else None
                            olmis_service = service_data['olmis_service']
                            services = olmis_service.split(',')
                            for service in services:
                                OVCCareServices(
                                    service_provided=service,
                                    service_provider=org_unit,
                                    # place_of_service = olmis_place_of_service,
                                    domain=olmis_domain,
                                    date_of_encounter_event=olmis_service_date,
                                    event=event_obj,
                                    service_grouping_id=ovc_care_services[0].service_grouping_id
                                ).save()

            msg = 'Saved Successfully'
            jsonResponse.append({'msg': msg})
    except Exception as e:
        print(e)
        msg = 'Save Error: (%s)' % (str(e))
        print(msg)
    jsonResponse.append({'msg': msg})
    return JsonResponse(jsonResponse, content_type='application/json', safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_form1a(request, id, btn_event_type, btn_event_pk):
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    form = OVCF1AForm(initial={'person': id})
    event_obj = OVCCareEvents.objects.get(pk=btn_event_pk)
    event_id = uuid.UUID(btn_event_pk)
    d_event = OVCCareEvents.objects.filter(pk=event_id)[0].timestamp_created
    delta = get_days_difference(d_event)
    print("stop 1")
    print(delta)

    print('check delta')
    print(delta)
    if delta < 90:
        if btn_event_type == 'ASSESSMENT':
            ovc_care_assessments = OVCCareAssessment.objects.filter(event=event_obj)

            service_type_list = []
            olmis_assessment_domain_list = get_list(
                'olmis_assessment_domain_id', 'Please Select')
            date_of_event_edit = event_obj.date_of_event
            for ovc_care_assessment in ovc_care_assessments:
                domain_entry = {}
                assessment_entry = []
                domain_full_name = [domain for domain in olmis_assessment_domain_list if
                                    domain[0] == ovc_care_assessment.domain]

                assessment_entry.append(domain_full_name[0][1])
                assessment_entry.append(translate(ovc_care_assessment.service))
                assessment_entry.append(translate(ovc_care_assessment.service_status))
                domain_entry[ovc_care_assessment.assessment_id] = assessment_entry
                service_type_list.append(domain_entry)

                form = OVCF1AForm(initial={'person': id})
                date_of_event_edit = str(date_of_event_edit)
                print(service_type_list)
            return render(request,
                          'forms/edit_form1a.html',
                          {'form': form, 'init_data': init_data,
                           'vals': vals, 'event_pk': btn_event_pk, 'event_type': btn_event_type,
                           'service_type_list': service_type_list, 'date_of_event_edit': date_of_event_edit})


        elif btn_event_type == 'CRITICAL':
            print('---------------- stop point 1')
            critical_events = OVCCareEAV.objects.filter(event=event_obj)
            critical_events_lst = ''
            loop_count = 0
            for critical_event in critical_events:
                if loop_count == 0:
                    critical_events_lst = critical_events_lst + str(critical_event.value)
                    loop_count = loop_count + 1
                else:
                    critical_events_lst = critical_events_lst + ',' + str(critical_event.value)
            date_of_event_edit = str(event_obj.date_of_event)
            return render(request,
                          'forms/edit_form1a.html',
                          {'form': form, 'init_data': init_data,
                           'critical_events_lst': critical_events_lst, 'vals': vals, 'event_pk': btn_event_pk,
                           'event_type': btn_event_type, 'date_of_event_edit': date_of_event_edit})

        elif btn_event_type == 'SERVICES':
            date_of_event_edit = str(event_obj.date_of_event)
            services_list = []
            ## get Services
            ovccareservices = OVCCareServices.objects.filter(event=event_obj, is_void=False)
            olmis_domain_list = get_list('olmis_domain_id', 'Please Select')
            for ovccareservice in ovccareservices:
                service = {}
                assessment_entry = []
                domain_full_name = [domain for domain in olmis_domain_list if
                                    domain[0] == ovccareservice.domain]
                print(ovccareservice.domain)
                print('')
                print(olmis_domain_list)
                print('')
                print(domain_full_name)
                service['id'] = ovccareservice.service_id
                service['detail'] = translate(ovccareservice.service_provided)
                service['date'] = (str(ovccareservice.date_of_encounter_event))
                service['domain'] = domain_full_name[0][1]
                services_list.append(service)
            return render(request,
                          'forms/edit_form1a.html',
                          {'form': form, 'init_data': init_data,
                           'vals': vals, 'event_pk': btn_event_pk, 'event_type': btn_event_type,
                           'services_list': services_list, 'date_of_event_edit': date_of_event_edit})

        else:
            date_of_event_edit = str(event_obj.date_of_event)
            priority_lists = []
            olmis_domain_list = get_list('olmis_domain_id', 'Please Select')
            ## get Prioritys
            ovcprioritys = OVCCarePriority.objects.filter(event=event_obj, is_void=False)
            for ovcpriority in ovcprioritys:
                priorty = {}
                domain_full_name = [domain for domain in olmis_domain_list if
                                    domain[0] == ovcpriority.domain]
                priorty['id'] = str(ovcpriority.pk)
                priorty['domain'] = domain_full_name[0][1]
                priorty['need'] = translate(ovcpriority.service)
                priority_lists.append(priorty)
            print(priority_lists)
            return render(request,
                          'forms/edit_form1a.html',
                          {'form': form, 'init_data': init_data,
                           'vals': vals, 'event_pk': btn_event_pk, 'event_type': btn_event_type,
                           'priority_lists': priority_lists, 'date_of_event_edit': date_of_event_edit})
    else:
        err_msgg = "Can't alter after 90 days"
        # return HttpResponseRedirect(reverse('form1a_events', args=(id,)))
        return render(request,
                      'forms/form1a_events.html',
                      {'form': form, 'init_data': init_data,
                       'vals': vals, 'event_pk': btn_event_pk, 'event_type': btn_event_type, 'err_msgg': err_msgg})


@login_required(login_url='/')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_form1a(request, id, btn_event_type, btn_event_pk):
    jsonForm1AData = []
    msg = ''
    try:
        event_id = uuid.UUID(btn_event_pk)
        d_event = OVCCareEvents.objects.filter(pk=event_id)[0].timestamp_created
        delta = get_days_difference(d_event)
        if delta < 90:
            event = OVCCareEvents.objects.filter(pk=event_id)
            print("we are here")
            if event:
                if btn_event_type == 'ASSESSMENT':
                    OVCCareAssessment.objects.filter(event=event).delete()
                elif btn_event_type == 'PRIORITY':
                    OVCCarePriority.objects.filter(event=event).delete()
                elif 'CRITICAL' in btn_event_type:
                    OVCCareEAV.objects.filter(event=event).delete()
                elif btn_event_type == 'SERVICES':
                    OVCCareServices.objects.filter(event=event).delete()
                msg = 'Deleted successfully'
        else:
            msg = "Can't delete after 90 days"
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
    jsonForm1AData.append({'msg': msg})
    return JsonResponse(jsonForm1AData,
                        content_type='application/json',
                        safe=False)


@login_required(login_url='/')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_form1b(request, id, btn_event_pk):
    jsonForm1BData = []
    msg = ''
    try:
        event_id = uuid.UUID(btn_event_pk)
        d_event = OVCCareEvents.objects.filter(
            pk=event_id).first().timestamp_created
        delta = get_days_difference(d_event)
        if delta < 90:
            event = OVCCareEvents.objects.filter(pk=event_id)
            msg = "Deleted successfully"
            if event:
                # Soft delete assessment
                assesm = OVCCareAssessment.objects.filter(event_id=event_id)
                if assesm:
                    # assesm.delete()
                    assesm.update(is_void=True)
                # Soft delete services
                servi = OVCCareServices.objects.filter(event_id=event_id)
                if servi:
                    # servi.delete()
                    servi.update(is_void=True)
                # Soft delete f1b
                f1bin = OVCCareF1B.objects.filter(event_id=event_id)
                if f1bin:
                    # f1bin.delete()
                    f1bin.update(is_void=True)
                # Soft delete critical events
                cevent = OVCCareEAV.objects.filter(event_id=event_id)
                if cevent:
                    cevent.update(is_void=True)
                # Soft delete event
                # event.delete()
                event.update(is_void=True)
                msg = "Event details successfully"
        else:
            msg = "Can't delete after 90 days"
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
    jsonForm1BData.append({'msg': msg})
    return JsonResponse(jsonForm1BData,
                        content_type='application/json',
                        safe=False)


@login_required(login_url='/')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_previous_event_entry(request, btn_event_type, entry_id):
    print("debug log ==========delete previous entry==========")
    jsonForm1AData = []
    try:
        entry_id = uuid.UUID(entry_id)
        if btn_event_type == 'ASSESSMENT':
            OVCCareAssessment.objects.filter(pk=entry_id).delete()
        elif btn_event_type == 'PRIORITY':
            OVCCarePriority.objects.filter(pk=entry_id).delete()
        elif btn_event_type == 'CRITICAL EVENT':
            OVCCareEAV.objects.filter(pk=entry_id).delete()
        elif btn_event_type == 'SERVICES':
            OVCCareServices.objects.filter(pk=entry_id).delete()
        msg = 'Deleted successfully'
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
    jsonForm1AData.append({'msg': msg})
    return JsonResponse(jsonForm1AData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_form1a(request):
    jsonForm1AData = []
    try:
        msg = 'The page you are looking for is under construction!'
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
    jsonForm1AData.append({'msg': msg})
    return JsonResponse(jsonForm1AData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_form1a_events(request):
    msg = ''
    jsonForm1AEventsData = []
    try:
        person = request.POST.get('person')
        ovccareevents = OVCCareEvents.objects.filter(
            person=person, event_type_id='FSAM').order_by('-date_of_event')

        for ovccareevent in ovccareevents:
            event_type = None
            event_details = None
            services = []
            event_keywords = []
            event_keyword_group = []
            assessments = []
            prioritys = []
            critical_events = []
            event_date = ovccareevent.date_of_event

            ## get Assessment
            ovccareassessments = OVCCareAssessment.objects.filter(event=ovccareevent.pk)
            for ovccareassessment in ovccareassessments:
                assessments.append(
                    translate(ovccareassessment.service) + '(' + translate(ovccareassessment.service_status) + ')')
                event_keywords.append(ovccareassessment.service)

            ## get CriticalEvents
            ovccriticalevents = OVCCareEAV.objects.filter(event=ovccareevent.pk)
            for ovccriticalevent in ovccriticalevents:
                critical_events.append(translate(ovccriticalevent.value))

            ## get Prioritys
            ovcprioritys = OVCCarePriority.objects.filter(event=ovccareevent.pk)
            for ovcpriority in ovcprioritys:
                prioritys.append(translate(ovcpriority.service))

            ## get Services
            ovccareservices = OVCCareServices.objects.filter(event=ovccareevent.pk)
            for ovccareservice in ovccareservices:
                services.append(translate(ovccareservice.service_provided))

            if (services):
                event_type = 'SERVICES'
                event_details = ', '.join(services)
            elif (assessments):
                event_type = 'ASSESSMENT'
                event_details = ', '.join(assessments)
                event_keyword_group = ', '.join(event_keywords)
            elif (prioritys):
                event_type = 'PRIORITY'
                event_details = ', '.join(prioritys)
            elif (critical_events):
                event_type = 'CRITICAL EVENT'
                event_details = ', '.join(critical_events)

            jsonForm1AEventsData.append({
                'event_pk': str(ovccareevent.pk),
                'event_type': event_type,
                'event_details': event_details,
                'event_keyword_group': event_keyword_group,
                'event_date': event_date.strftime('%d-%b-%Y')
            })
        # print jsonForm1AEventsData
        return JsonResponse(jsonForm1AEventsData,
                            content_type='application/json',
                            safe=False)
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
        jsonForm1AEventsData.append({'msg': msg})
        return JsonResponse(jsonForm1AEventsData,
                            content_type='application/json',
                            safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_form1b_events(request):
    msg = ''
    jsonForm1BEventsData = []
    try:
        person = request.POST.get('person')
        ovccareevents = OVCCareEvents.objects.filter(person=person, event_type_id='FM1B')
        for ovccareevent in ovccareevents:
            event_type = None
            event_details = None
            services = []
            event_keywords = []
            event_keyword_group = []
            assessments = []
            event_date = ovccareevent.date_of_event

            ## get Assessment
            ovccareassessments = OVCCareAssessment.objects.filter(event=ovccareevent.pk)
            for ovccareassessment in ovccareassessments:
                assessments.append(
                    translate(ovccareassessment.service) + '(' + translate(ovccareassessment.service_status) + ')')
                event_keywords.append(ovccareassessment.service)

            ## get Services
            ovccareservices = OVCCareServices.objects.filter(event=ovccareevent.pk)
            for ovccareservice in ovccareservices:
                services.append(translate(ovccareservice.service_provided))

            if (True):
                event_type = 'SERVICES'
                event_details = ', '.join(services)
            elif (False):
                event_type = 'ASSESSMENT'
                event_details = ', '.join(assessments)
                event_keyword_group = ', '.join(event_keywords)

            jsonForm1BEventsData.append({
                'event_pk': str(ovccareevent.pk),
                'event_type': event_type,
                'event_details': event_details,
                'event_keyword_group': event_keyword_group,
                'event_date': event_date.strftime('%d-%b-%Y')
            })
        print(jsonForm1BEventsData)
        return JsonResponse(jsonForm1BEventsData,
                            content_type='application/json',
                            safe=False)
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
        jsonForm1BEventsData.append({'msg': msg})
        return JsonResponse(jsonForm1BEventsData,
                            content_type='application/json',
                            safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_hhva(request, id):
    try:
        if request.method == 'POST':
            my_kvals = []
            event_type_id = 'FHSA'
            household_id = request.POST.get('household_id')
            date_of_hhva = request.POST.get('date_of_hhva')
            if date_of_hhva:
                date_of_hhva = convert_date(date_of_hhva)

            """ Save CSIEvent """
            event_counter = OVCCareEvents.objects.filter(
                event_type_id=event_type_id, person=id, is_void=False).count()
            ovccareevent = OVCCareEvents(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                date_of_event=date_of_hhva,
                created_by=request.user.id,
                # person=RegPerson.objects.get(pk=int(id)),
                house_hold=OVCHouseHold.objects.get(pk=household_id)
            )
            ovccareevent.save()
            new_pk = ovccareevent.pk

            # Household Individuals
            hhva_ha1_male = request.POST.get('hhva_ha1_male')
            hhva_ha1_female = request.POST.get('hhva_ha1_female')
            hhva_ha2_male = request.POST.get('hhva_ha2_male')
            hhva_ha2_female = request.POST.get('hhva_ha2_female')
            hhva_ha3_male = request.POST.get('hhva_ha3_male')
            hhva_ha3_female = request.POST.get('hhva_ha3_female')
            hhva_ha4_male = request.POST.get('hhva_ha4_male')
            hhva_ha4_female = request.POST.get('hhva_ha4_female')
            # ************************************************************
            my_kvals.append({"entity": "HA1M", "attribute": "HA1M", "value": hhva_ha1_male, "value_for": ''})
            my_kvals.append({"entity": "HA1F", "attribute": "HA1F", "value": hhva_ha1_female, "value_for": ''})
            my_kvals.append({"entity": "HA2M", "attribute": "HA2M", "value": hhva_ha2_male, "value_for": ''})
            my_kvals.append({"entity": "HA2F", "attribute": "HA2F", "value": hhva_ha2_female, "value_for": ''})
            my_kvals.append({"entity": "HA3M", "attribute": "HA3M", "value": hhva_ha3_male, "value_for": ''})
            my_kvals.append({"entity": "HA3F", "attribute": "HA3F", "value": hhva_ha3_female, "value_for": ''})
            my_kvals.append({"entity": "HA4M", "attribute": "HA4M", "value": hhva_ha4_male, "value_for": ''})
            my_kvals.append({"entity": "HA4F", "attribute": "HA4F", "value": hhva_ha4_female, "value_for": ''})

            # Water, Sanitation & Hygiene
            hhva_ha5 = request.POST.get('hhva_ha5')
            hhva_ha6 = request.POST.getlist('hhva_ha6')
            hhva_ha7 = request.POST.get('hhva_ha7')
            hhva_ha8 = request.POST.get('hhva_ha8')
            # ************************************************************
            my_kvals.append({"entity": "HA5", "attribute": "HA5", "value": hhva_ha5, "value_for": ''})
            for i, ha6 in enumerate(hhva_ha6):
                ha6 = ha6.split(',')
                for value in ha6:
                    my_kvals.append({"entity": "HA6", "attribute": "HA6", "value": value, "value_for": ''})
            my_kvals.append({"entity": "HA7", "attribute": "HA7", "value": hhva_ha7, "value_for": ''})
            my_kvals.append({"entity": "HA8", "attribute": "HA8", "value": hhva_ha8, "value_for": ''})

            # Shelter & Care
            hhva_ha9 = request.POST.get('hhva_ha9')
            hhva_wash_list = request.POST.get('hhva_wash_list')
            hhva_wash_data = json.loads(hhva_wash_list)
            # ************************************************************
            my_kvals.append({"entity": "HA9", "attribute": "HA9", "value": hhva_ha9, "value_for": ''})
            for data in hhva_wash_data:
                type_ = data["type"]
                condition = data["condition"]
                number = data["number"]
                my_kvals.append({"entity": 'HA10', "attribute": type_, "value": number, "value_for": 'NUMBER'})
                my_kvals.append({"entity": 'HA10', "attribute": type_, "value": condition, "value_for": 'CONDITION'})

            # Food Security & Nutrition
            hhva_ha11 = request.POST.get('hhva_ha11')
            hhva_ha12 = request.POST.get('hhva_ha12')
            # ************************************************************
            my_kvals.append({"entity": "HA11", "attribute": "HA11", "value": hhva_ha11, "value_for": ''})
            my_kvals.append({"entity": "HA12", "attribute": "HA12", "value": hhva_ha12, "value_for": ''})

            # Household Income & Property
            hhva_asset_list = request.POST.get('hhva_asset_list')
            hhva_asset_data = json.loads(hhva_asset_list)
            hhva_ha13 = request.POST.get('hhva_ha13')
            hhva_ha14 = request.POST.get('hhva_ha14')
            hhva_ha16 = request.POST.get('hhva_ha16')
            hhva_ha17 = request.POST.get('hhva_ha17')
            hhva_ha18 = request.POST.get('hhva_ha18')
            hhva_ha19 = request.POST.get('hhva_ha19')
            hhva_ha20 = request.POST.get('hhva_ha20')
            hhva_ha21 = request.POST.getlist('hhva_ha21')
            # ************************************************************
            for data in hhva_asset_data:
                asset = data["asset"]
                number = data["number"]
                size = data["size"]
                my_kvals.append({"entity": 'HA15', "attribute": asset, "value": number, "value_for": 'NUMBER'})
                my_kvals.append({"entity": 'HA15', "attribute": asset, "value": size, "value_for": 'SIZE'})
            my_kvals.append({"entity": "HA13", "attribute": "HA11", "value": hhva_ha13, "value_for": ''})
            my_kvals.append({"entity": "HA14", "attribute": "HA14", "value": hhva_ha14, "value_for": ''})
            my_kvals.append({"entity": "HA16", "attribute": "HA16", "value": hhva_ha16, "value_for": ''})
            my_kvals.append({"entity": "HA17", "attribute": "HA17", "value": hhva_ha17, "value_for": ''})
            my_kvals.append({"entity": "HA18", "attribute": "HA18", "value": hhva_ha18, "value_for": ''})
            my_kvals.append({"entity": "HA19", "attribute": "HA19", "value": hhva_ha19, "value_for": ''})
            my_kvals.append({"entity": "HA20", "attribute": "HA20", "value": hhva_ha20, "value_for": ''})
            for i, ha21 in enumerate(hhva_ha21):
                ha21 = ha21.split(',')
                for value in ha21:
                    my_kvals.append({"entity": "HA21", "attribute": "HA21", "value": value, "value_for": ''})

            # Health Services and Health Seeking Behaviours
            hhva_ha22 = request.POST.get('hhva_ha22')
            hhva_ha23 = request.POST.get('hhva_ha23')
            hhva_ha24 = request.POST.get('hhva_ha24')
            hhva_ha25 = request.POST.get('hhva_ha25')
            hhva_ha26_male = request.POST.get('hhva_ha26_male')
            hhva_ha26_female = request.POST.get('hhva_ha26_female')
            hhva_ha27_male = request.POST.get('hhva_ha27_male')
            hhva_ha27_female = request.POST.get('hhva_ha27_female')
            # ************************************************************
            my_kvals.append({"entity": "HA22", "attribute": "HA22", "value": hhva_ha22, "value_for": ''})
            my_kvals.append({"entity": "HA23", "attribute": "HA23", "value": hhva_ha23, "value_for": ''})
            my_kvals.append({"entity": "HA24", "attribute": "HA24", "value": hhva_ha24, "value_for": ''})
            my_kvals.append({"entity": "HA25", "attribute": "HA25", "value": hhva_ha25, "value_for": ''})
            my_kvals.append({"entity": "HA26M", "attribute": "HA26M", "value": hhva_ha26_male, "value_for": ''})
            my_kvals.append({"entity": "HA26F", "attribute": "HA26F", "value": hhva_ha26_female, "value_for": ''})
            my_kvals.append({"entity": "HA27M", "attribute": "HA27M", "value": hhva_ha27_male, "value_for": ''})
            my_kvals.append({"entity": "HA27F", "attribute": "HA27F", "value": hhva_ha27_female, "value_for": ''})

            # Protection
            hhva_ha28 = request.POST.getlist('hhva_ha28')
            # ************************************************************
            for i, ha28 in enumerate(hhva_ha28):
                ha28 = ha28.split(',')
                for value in ha28:
                    my_kvals.append({"entity": "HA28", "attribute": "HA28", "value": value, "value_for": ''})

            # Other Services
            hhva_ha29 = request.POST.getlist('hhva_ha29')
            hhva_ha30 = request.POST.getlist('hhva_ha30')
            # ************************************************************
            for i, ha29 in enumerate(hhva_ha29):
                ha29 = ha29.split(',')
                for value in ha29:
                    my_kvals.append({"entity": "HA29", "attribute": "HA29", "value": value, "value_for": ''})
            for i, ha30 in enumerate(hhva_ha30):
                ha30 = ha30.split(',')
                for value in ha30:
                    my_kvals.append({"entity": "HA30", "attribute": "HA30", "value": value, "value_for": ''})

            # Household Priorities
            hhva_ha31 = request.POST.getlist('hhva_ha31')
            for i, ha31 in enumerate(hhva_ha31):
                ha31 = ha31.split(',')
                for value in ha31:
                    my_kvals.append({"entity": "HA31", "attribute": "HA31", "value": value, "value_for": ''})

            print('my_kvals : %s' % my_kvals)
            for kvals in my_kvals:
                key = kvals["entity"]
                attribute = kvals["attribute"]
                value = kvals["value"]
                value_for = kvals["value_for"] if kvals["value_for"] else None
                OVCCareEAV(
                    entity=key,
                    attribute=attribute,
                    value=value,
                    value_for=value_for,
                    event=OVCCareEvents.objects.get(pk=new_pk)
                ).save()

            msg = 'Household Vulnerability Assessment save successful'
            messages.add_message(request, messages.INFO, msg)
            url = reverse('ovc_view', kwargs={'id': id})
            # return HttpResponseRedirect(reverse(forms_registry))
            return HttpResponseRedirect(url)
    except Exception as e:
        msg = 'Household Vulnerability Assessment save error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        print('Error saving HHVA : %s' % str(e))
        return HttpResponseRedirect(reverse(forms_registry))

    # get household members/ caretaker/ household_id
    household_id = None
    try:
        ovcreg = get_object_or_404(OVCRegistration, person_id=id, is_void=False)
        caretaker_id = ovcreg.caretaker_id if ovcreg else None
        ovchh = get_object_or_404(OVCHouseHold, head_person=caretaker_id, is_void=False)
        household_id = ovchh.id if ovchh else None
    except Exception as e:
        print(str(e))
        msg = 'Error getting household identifier: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))

        # get relations
    guardians = RegPersonsGuardians.objects.select_related().filter(
        child_person=id, is_void=False, date_delinked=None)
    siblings = RegPersonsSiblings.objects.select_related().filter(
        child_person=id, is_void=False, date_delinked=None)
    # Reverse relationship
    osiblings = RegPersonsSiblings.objects.select_related().filter(
        sibling_person=id, is_void=False, date_delinked=None)
    oguardians = RegPersonsGuardians.objects.select_related().filter(
        guardian_person=id, is_void=False, date_delinked=None)

    # get child data
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id', 'relationship_type_id']
    vals = get_dict(field_name=check_fields)
    form = OVCHHVAForm(initial={'household_id': household_id})
    return render(request,
                  'forms/new_hhva.html',
                  {
                      'form': form,
                      'init_data': init_data,
                      'vals': vals,
                      'person': id,
                      'guardians': guardians,
                      'siblings': siblings,
                      'osiblings': osiblings,
                      'oguardians': oguardians
                  })


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_hhva(request, id):
    try:
        msg = 'The page you are looking for is under construction!'
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    except Exception as e:
        raise e


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_hhva(request, id):
    try:
        msg = 'The page you are looking for is under construction!'
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    except Exception as e:
        raise e


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_hhva(request, id):
    try:
        msg = 'The page you are looking for is under construction!'
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    except Exception as e:
        raise e


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_bursary(request):
    try:
        if request.method == 'POST':
            person_id = request.POST.get('person_id')
            bursary_id = request.POST.get('bursary_id')
            jsonBursaryData = []

            bursary_data = OVCBursary.objects.filter(
                person_id=person_id,
                is_void=False).order_by('-timestamp_created')

            school_data = OVCEducationFollowUp.objects.filter(
                person=person_id,
                is_void=False).values_list('school_id', flat=True)

            if bursary_data:
                for bursarydata in bursary_data:
                    bdt = (bursarydata.disbursement_date).strftime('%d-%b-%Y')
                    jsonBursaryData.append({
                        'pk': str(bursarydata.bursary_id),
                        'person_id': bursarydata.person_id,
                        'bursary_type': translate(bursarydata.bursary_type),
                        'disbursement_date': bdt,
                        'amount': bursarydata.amount,
                        'year': bursarydata.year,
                        'school_name': translate_school(str(school_data[0])),
                        'term': translate(bursarydata.term)
                    })

    except Exception as e:
        print('Load Bursary Information Error: %s' % str(e))
    return JsonResponse(jsonBursaryData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_countries(request):
    try:
        jsonCountriesData = []
        for country_code, country_name in COUNTRIES.items():
            # print country_code, country_name
            jsonCountriesData.append({
                'country_code': country_code,
                'country_name': country_name
            })
    except Exception as e:
        print('Load Countries Information Error: %s' % str(e))
    return JsonResponse(jsonCountriesData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_casehistory(request):
    try:
        jsonCaseHistoryData = []
        jsonOrgUnitContacts = []
        person_id = request.POST.get('person_id')
        querysets = OVCCaseGeo.objects.select_related().filter(
            person=person_id, is_void=False)

        if querysets:
            for queryset in querysets:
                orgunit_querysets = RegOrgUnitContact.objects.filter(
                    org_unit=queryset.report_orgunit.pk, is_void=False)
                for orgunit_queryset in orgunit_querysets:
                    jsonOrgUnitContacts.append({
                        'contact_detail_type_id': translate(orgunit_queryset.contact_detail_type_id),
                        'contact_detail': orgunit_queryset.contact_detail
                    })

                jsonCaseHistoryData.append({
                    'case_serial': queryset.case_id.case_serial,
                    'report_orgunit': queryset.report_orgunit.org_unit_name,
                    'orgunit_contacts': jsonOrgUnitContacts,
                })
        else:
            jsonCaseHistoryData.append({
                'case_serial': ''
            })
        print('jsonCaseHistoryData: %s' % jsonCaseHistoryData)

    except Exception as e:
        print('Load Case History Information Error: %s' % str(e))
    return JsonResponse(jsonCaseHistoryData,
                        content_type='application/json',
                        safe=False)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_schools(request):
    try:
        jsonSchoolsData = []

        schoolsdata = SchoolList.objects.all().order_by('-school_name')
        if schoolsdata:
            for schooldata in schoolsdata:
                jsonSchoolsData.append({
                    'pk': str(schooldata.school_id),
                    'school_name': schooldata.school_name,
                    'school_subcounty': translate_geo(schooldata.school_subcounty_id),
                    'school_ward': translate_geo(schooldata.school_ward_id)
                })

    except Exception as e:
        print('Load Schools Information Error: %s' % str(e))
    return JsonResponse(jsonSchoolsData,
                        content_type='application/json',
                        safe=False)


def manage_case_events(request):
    try:
        if request.method == 'POST':
            case_id = request.POST.get('case_id')
            jsonCaseEventsData = []
            case_event_type = None

            # OVCCaseEvents
            c_events = OVCCaseEvents.objects.filter(
                case_id=case_id, is_void=False).order_by('-timestamp_created')

            if c_events:
                for c_event in c_events:
                    case_event_description = []
                    case_event_category = []
                    case_event_date = []
                    print('ev', c_event.case_event_type_id, c_event.case_event_id)

                    if c_event.case_event_type_id == 'SERVICES':
                        case_event_type = 'SERVICES'
                        servicesData = OVCCaseEventServices.objects.filter(
                            case_event_id=c_event.case_event_id, is_void=False)
                        print(1, servicesData)
                        if servicesData:
                            for serviceData in servicesData:
                                print('s', serviceData.case_category_id)
                                case_event_category = translate(
                                    translate_case(str(serviceData.case_category_id)))
                                case_event_description.append(
                                    translate(serviceData.service_provided))
                                case_event_date.append(
                                    serviceData.date_of_encounter_event)

                    courtevents = ['COURT MENTION', 'COURT HEARING',
                                   'COURT PLEA', 'COURT APPLICATION']
                    notes = c_event.case_event_notes
                    case_notes = '- %s' % (notes) if notes else ''
                    if c_event.case_event_type_id in courtevents:
                        case_event_type = c_event.case_event_type_id
                        courtsData = OVCCaseEventCourt.objects.filter(
                            case_event_id=c_event.case_event_id)

                        courtorders = []
                        for courtData in courtsData:
                            if courtData.court_order:
                                courtorders.append(
                                    translate(courtData.court_order))
                            case_event_category = translate(
                                translate_case(str(courtData.case_category_id)))
                        print('case_event_category - %s' % case_event_category)
                        event_description = ''
                        if courtorders:
                            event_description = ','.join(courtorders)
                        else:
                            """ Get Court Data For Court Session Types Mention) """
                            if c_event.next_hearing_date:
                                event_description = 'Adjournment, next hearing date is ' + \
                                    (c_event.next_hearing_date).strftime(
                                        '%d-%b-%Y')
                            if c_event.next_mention_date:
                                event_description = 'Mention, next mention date is ' + \
                                    (c_event.next_mention_date).strftime(
                                        '%d-%b-%Y')
                            if c_event.plea_taken:
                                event_description = 'Plea taken (%s), next mention date is %s' % (translate(
                                    c_event.plea_taken), (c_event.next_mention_date).strftime('%d-%b-%Y'))
                            if c_event.application_outcome:
                                ap = '' if c_event.application_outcome == 'APGR' else 'NOT '
                                event_description = 'Application %sGranted' % (ap)
                        event_description = '%s %s' % (event_description, case_notes)
                        case_event_description.append(event_description)
                        case_event_date.append(c_event.date_of_event)
                    if c_event.case_event_type_id == 'PLACEMENT':
                        case_event_type = 'PLACEMENT'
                        placementsData = OVCPlacement.objects.filter(
                            case_event_id=c_event.case_event_id)
                        if placementsData:
                            for placementData in placementsData:
                                case_event_description.append(
                                    placementData.residential_institution)
                                case_event_date.append(
                                    placementData.timestamp_created)

                    if c_event.case_event_type_id == 'CLOSURE':
                        case_event_type = 'CLOSURE'
                        closuresData = OVCCaseEventClosure.objects.filter(
                            case_event_id=c_event.case_event_id, is_void=False)
                        if closuresData:
                            for closureData in closuresData:
                                case_event_description.append(
                                    closureData.case_closure_notes)
                                case_event_date.append(
                                    closureData.date_of_case_closure)
                            case_event_category = 'ALL CASES'

                    if c_event.case_event_type_id == 'SUMMON':
                        case_event_type = 'SUMMON'
                        summonsData = OVCCaseEventSummon.objects.filter(
                            case_event_id=c_event.case_event_id, is_void=False)

                        if summonsData:
                            for summonData in summonsData:
                                # summon_outcome = summonData.honoured
                                # summon_outcome = '(Honoured)' if summon_outcome else '(Not Honoured)'
                                case_event_description.append(
                                    summonData.summon_note)
                                case_event_date.append(c_event.date_of_event)
                            case_event_category = 'ALL CASES'
                    print('case_event_date', case_event_date)
                    if case_event_date:
                        case_event_date = case_event_date[0].strftime('%d-%b-%Y')
                    else:
                        case_event_date = 'Not Provided'
                    jsonCaseEventsData.append({
                        'case_event_type': case_event_type,
                        'case_event_id': str(c_event.case_event_id),
                        'case_event_category': case_event_category,
                        'case_event_description': case_event_description,
                        'case_event_date': str(case_event_date)
                    })

            # OVCReferral
            ovcreferrals = OVCReferral.objects.filter(
                case_id=case_id, is_void=False).order_by('-timestamp_created')
            if ovcreferrals:
                for ovcreferral in ovcreferrals:
                    case_category = ovcreferral.case_category_id
                    case_event_category = translate((translate_case(
                        ovcreferral.case_category_id))) if case_category else 'NOT ATTACHED'

                    refferal_enddate = (ovcreferral.refferal_enddate).strftime(
                        '%d-%b-%Y') if ovcreferral.refferal_enddate else 'NOT COMPLETED'
                    jsonCaseEventsData.append({
                        'case_event_type': 'REFERRAL',
                        'case_event_id': 'NONE',
                        'case_event_category': str(case_event_category),
                        'case_event_description': translate(ovcreferral.refferal_to),
                        'case_event_date': refferal_enddate
                    })

    except Exception as e:
        print('Load Case Events Error: %s' % str(e))
    return JsonResponse(jsonCaseEventsData,
                        content_type='application/json',
                        safe=False)


def manage_refferal(request):
    try:
        if request.method == 'POST':
            now = timezone.now()
            action = request.POST.get('action')
            jsonManageReferralData = []
            case_id = request.POST.get('case_id')
            referralactors_data = request.POST.get('ReferralsData')
            referral_grouping_id = new_guid_32()
            if(referralactors_data):
                referralactors_data = json.loads(referralactors_data)
                refferal_actor_type = referralactors_data['refferals_actor']
                refferral_actor_description = referralactors_data[
                    'refferals_actor_specify']
                refferal_to = referralactors_data['refferals_made']
                case_category = referralactors_data['refferal_case']
                ovccr = OVCCaseRecord.objects.get(case_id=case_id)
                referral_grouping_id = new_guid_32()
                OVCReferral(
                    case_id=OVCCaseRecord.objects.get(pk=ovccr.case_id),
                    refferal_actor_type=refferal_actor_type,
                    refferal_actor_specify=refferral_actor_description,
                    refferal_to=refferal_to,
                    referral_grouping_id=referral_grouping_id,
                    case_category=OVCCaseCategory.objects.get(
                        pk=case_category),
                    timestamp_created=now,
                    person=RegPerson.objects.get(pk=int(ovccr.person_id))).save()
            jsonManageReferralData.append(
                {'referral_grouping_id': referral_grouping_id})
    except Exception as e:
        print('Save/Manage Referral Error: %s' % str(e))
    return JsonResponse(jsonManageReferralData,
                        content_type='application/json',
                        safe=False)


def manage_refferal001(request):
    try:
        if request.method == 'POST':
            # Remove Existing Referral
            referral_grouping_id = request.POST.get('referral_grouping_id')
            OVCReferral.objects.filter(
                referral_grouping_id=referral_grouping_id).update(is_void=True)
    except Exception as e:

        print('Manage Referral001 Error: %s' % str(e))
    return HttpResponse('Manage Encounter001 Success : List.Append()')


def manage_refferal002(request):
    try:
        if request.method == 'POST':
            jsonReferralData = []
            case_id = request.POST.get('case_id')

            # Get Referrals to Use to return json
            ovcreferrals = OVCReferral.objects.filter(
                case_id=case_id, is_void=False)
            for ovcreferral in ovcreferrals:
                jsonReferralData.append({
                    'refferal_id': str(ovcreferral.refferal_id),
                    'refferal_to': translate(ovcreferral.refferal_to),
                    'refferal_status': ovcreferral.refferal_status,
                    'refferal_enddate': ovcreferral.refferal_enddate,
                    'refferal_case_category': str(ovcreferral.case_category_id)})
    except Exception as e:
        print('Manage Referral002 Error: %s' % str(e))
    return JsonResponse(jsonReferralData,
                        content_type='application/json',
                        safe=False)


def manage_refferal003(request):
    try:
        if request.method == 'POST':
            now = timezone.now()
            jsonReferralData = []
            case_category_id = None
            refferal_enddate1 = None
            jsonObject = request.POST.get('ReferralsData')
            referrals_data = json.loads(jsonObject)

            if referrals_data:
                refferal_id = referrals_data['refferal_id']
                case_category_ids = referrals_data['case_category_ids']
                refferal_enddate2 = referrals_data['date_referral_completed']

                # Attach CaseCategoryId if Any
                if case_category_ids:
                    case_category_id = case_category_ids

                # Attach refferal_enddate if Any
                if refferal_enddate2 == 'Referral End Date':
                    refferal_enddate2 = None
                if refferal_enddate2:
                    refferal_enddate1 = refferal_enddate2
                    refferal_enddate1 = convert_date(refferal_enddate1)
                    refferal_status = 'COMPLETED'

                # Update OVCReferral Model
                ovcref = OVCReferral.objects.get(refferal_id=refferal_id)
                ovcref.refferal_enddate = refferal_enddate1
                ovcref.case_category = OVCCaseCategory.objects.get(
                    pk=case_category_id)
                ovcref.refferal_status = refferal_status
                ovcref.save(
                    update_fields=[
                        'refferal_enddate',
                        'case_category',
                        'refferal_status'
                    ])
    except Exception as e:
        print('Manage Referral003 Error: %s' % str(e))
    return JsonResponse(jsonReferralData,
                        content_type='application/json',
                        safe=False)


def manage_encounters001(request):
    try:
        if request.method == 'POST':
            jsonObject = request.POST.get('EncountersData')
            data = json.loads(jsonObject)
            jsonObjectArrayServices.append(data)
        else:
            print('Not POST')
    except Exception as e:
        print('Manage Encounter001 Error: %s' % str(e))
    return HttpResponse('Manage Encounter001 Success : List.Append()')


def manage_encounters004(request):
    # Pull Case Categories From Db on Edit #
    try:
        service_provided_list = []
        place_of_service_list = []
        date_of_encounter_event_list = []
        jsonServicesData = []

        if request.method == 'POST':
            service_grouping_id = request.POST.get('service_grouping_id')

            ovcservices = OVCCaseEventServices.objects.filter(
                service_grouping_id=service_grouping_id, is_void=False)

            for ovcservice in ovcservices:
                service_provided_list.append(str(ovcservice.service_provided))
                place_of_service_list.append(str(ovcservice.place_of_service))
                date_of_encounter_event_list.append(
                    str(ovcservice.date_of_encounter_event))
            jsonServicesData.append({'service_provided_list': service_provided_list,
                                     'place_of_service_list': place_of_service_list,
                                     'date_of_encounter_event_list': date_of_encounter_event_list
                                     })
        else:
            print('Not POST')
    except Exception as e:
        print('Pull Encounters From Db on Edit: %s' % str(e))
    return JsonResponse(jsonServicesData, content_type='application/json',
                        safe=False)


def manage_casecategory001(request):
    try:
        if request.method == 'POST':
            jsonCaseSubCategoriesData = []
            case_category_id = request.POST.get('case_category_id')

            if case_category_id:
                # Get item_sub_category
                casesubcategory = SetupList.objects.get(
                    field_name='case_category_id', item_id=case_category_id)
                item_sub_category = casesubcategory.item_sub_category

                if not item_sub_category:
                    jsonCaseSubCategoriesData.append({'item_sub_category': casesubcategory.item_description,
                                                      'item_sub_category_id': casesubcategory.item_id,
                                                      'status': 0})
                else:
                    casesubcategories = SetupList.objects.filter(
                        field_name=item_sub_category)
                    for casesubcategory in casesubcategories:
                        jsonCaseSubCategoriesData.append({'item_sub_category': casesubcategory.item_description,
                                                          'item_sub_category_id': casesubcategory.item_id,
                                                          'status': 1})
    except Exception as e:
        print('Error >>  %s' % str(e))
    return JsonResponse(jsonCaseSubCategoriesData, content_type='application/json',
                        safe=False)


def manage_casecategory002(request):
    try:
        if request.method == 'POST':
            index = int(request.POST.get('index'))
            jsonObjectArray.pop(index - 1)
        else:
            print('Not POST')
    except Exception as e:
        print('Manage Referral002 Error: %s' % str(e))
    return HttpResponse('Manage Referral002 Success : List.Remove()')


def manage_casecategory003(request):
    # global jsonObjectArray
    jsonObjectArray = []
    return HttpResponse('Manage Referral003 Success : List.Remove(All)')


def manage_casecategory004(request):
    # Pull Case Categories From Db on Edit #
    try:
        case_category_list = []
        date_of_event_list = []
        jsonCaseCategorysData = []

        if request.method == 'POST':
            case_grouping_id = request.POST.get('span_case_grouping_id')

            ovcccats = OVCCaseCategory.objects.filter(
                case_grouping_id=case_grouping_id, is_void=False)

            for ovcccat in ovcccats:
                case_category_list.append(str(ovcccat.case_category))
                date_of_event_list.append(str(ovcccat.date_of_event))

            jsonCaseCategorysData.append({'case_category_list': case_category_list,
                                          'date_of_event_list': date_of_event_list
                                          })

        else:
            print('Not POST')
    except Exception as e:
        print('Pull Case Categories From Db on Edit: %s' % str(e))
    return JsonResponse(jsonCaseCategorysData, content_type='application/json',
                        safe=False)


def manage_service_category(request):
    try:
        if request.method == 'POST':
            jsonServiceCategoriesData = []
            domain_id = request.POST.get('domain_id')
            index = int(request.POST.get('index'))

            if domain_id:
                if index == 1:
                    # Get services
                    servicecategory = SetupList.objects.get(
                        field_name='olmis_domain_id', item_id=domain_id)
                    service_sub_category = servicecategory.item_sub_category

                    if not service_sub_category:
                        jsonServiceCategoriesData.append({'item_sub_category': servicecategory.item_description,
                                                          'item_sub_category_id': servicecategory.item_id,
                                                          'status': 0})
                    else:
                        servicecategories = SetupList.objects.filter(
                            field_name=service_sub_category)
                        for servicecategory in servicecategories:
                            jsonServiceCategoriesData.append({'item_sub_category': servicecategory.item_description,
                                                              'item_sub_category_id': servicecategory.item_id,
                                                              'status': 1})

                if index == 2:
                    # Get assessments
                    assessmentcategory = SetupList.objects.get(
                        field_name='olmis_assessment_domain_id', item_id=domain_id)
                    assessment_sub_category = assessmentcategory.item_sub_category
                    print('assessmentcategory.item_sub_category -- %s' % assessmentcategory.item_sub_category)

                    if not assessment_sub_category:
                        jsonServiceCategoriesData.append({'item_sub_category': assessmentcategory.item_description,
                                                          'item_sub_category_id': str(assessmentcategory.item_id),
                                                          'status': 0})
                    else:
                        assessmentcategories = SetupList.objects.filter(
                            field_name=assessment_sub_category)
                        for assessmentcategory in assessmentcategories:
                            jsonServiceCategoriesData.append({'item_sub_category': assessmentcategory.item_description,
                                                              'item_sub_category_id': str(assessmentcategory.item_id),
                                                              'status': 1})
                if index == 3:
                    # Get fieldname
                    setuplist = SetupList.objects.filter(
                        item_id=domain_id, field_name__icontains='olmis')

                    for s in setuplist:
                        # Get assessments service status
                        assessmentstatuscategorys = SetupList.objects.filter(
                            field_name='' + s.item_sub_category + '')
                        if assessmentstatuscategorys:
                            for assessmentstatuscategory in assessmentstatuscategorys:
                                jsonServiceCategoriesData.append({'item_sub_category': assessmentstatuscategory.item_description,
                                                                  'item_sub_category_id': str(assessmentstatuscategory.item_id),
                                                                  'status': 1})
                if index == 4:
                    data_list = request.POST.get('domain_id')
                    if data_list:
                        _data = json.loads(data_list)
                        _item_ids = []
                        for _data_ in _data:
                            _service = _data_['olmis_priority_service']

                            # . . . not comma separated
                            if ',' not in _service:
                                _item_ids.append(_service)
                            else:
                                _itemx = _service.split(",")
                                for _itemx_ in _itemx:
                                    _item_ids.append(_itemx_)
                        for _item_id in _item_ids:
                            setuplist = SetupList.objects.filter(
                                item_id=_item_id,
                                field_name__icontains='olmis')
                            for s in setuplist:
                                jsonServiceCategoriesData.append(
                                    {'item_sub_category': s.item_description,
                                    'item_sub_category_id': str(s.item_id),
                                    'status': 1})
    except Exception as e:
        print('Error >>  %s' % str(e))
        raise e
    return JsonResponse(
        jsonServiceCategoriesData, content_type='application/json', safe=False)


def manage_form_type(request):
    jsonFormTypeData = []
    try:
        user_id = request.user.id
        reg_ovc = request.session.get('reg_ovc')
        ovc_forms = get_list('ovc_form_type_id', 'Please Select')
        cpims_forms = get_list('form_type_id', 'Please Select')
        all_forms = ovc_forms + cpims_forms
        if(reg_ovc) or (user_id == 1):
            d = dict(all_forms)
            jsonFormTypeData = [{"value": i, "label": j} for i, j in d.items()]
        else:
            d = dict(cpims_forms)
            jsonFormTypeData = [{"value": i, "label": j} for i, j in d.items()]
    except Exception as e:
        raise e
    return JsonResponse(jsonFormTypeData, content_type='application/json',
                        safe=False)


def getJsonObject001(request):
    jsonCaseCategories = []

    try:
        if request.method == 'POST':
            case_id = request.POST.get('case_id')
            action = int(request.POST.get('action'))

            if action == 1:
                # Load for CaseEvents
                ovcccats = OVCCaseCategory.objects.filter(
                    case_id=case_id, is_void=False)
                if ovcccats:
                    for ovcccat in ovcccats:
                        jsonCaseCategories.append(
                            {'case_category_id': str(ovcccat.case_category_id),
                            'case_category': translate(ovcccat.case_category)})
            if action == 2:
                # Load for ResidentialPlacementFollowup
                person = request.POST.get('person')
                ovcccats = OVCCaseCategory.objects.filter(
                    person=person, is_void=False)
                if ovcccats:
                    for ovcccat in ovcccats:
                        jsonCaseCategories.append(
                            {'case_category_id': str(ovcccat.case_category_id),
                            'case_category': translate(ovcccat.case_category)})
        else:
            print('getJsonObject001 - Not a POST')
    except Exception as e:
        print('Error: %s' % str(e))
    return JsonResponse(jsonCaseCategories, content_type='application/json',
                        safe=False)


@login_required
def new_bursary(request, id):
    """
    Method to do presidential Bursary
    """
    try:
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        person = RegPerson.objects.get(id=id)
        if request.method == 'POST':
            save_bursary(request, id)
            msg = 'Form Saved Successfully'
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseRedirect(reverse(background_details))
        form = GOKBursaryForm(
            initial={'person_type': 'TBVC'}, data=request.POST)
        return render(request, 'forms/bursary/new.html',
                      {'status': 200, 'form': form, 'child': person,
                       'vals': vals})
    except Exception as e:
        raise e
    else:
        pass


@login_required
def case_info(request, case_id):
    """Method to save case information."""
    try:
        check_fields = ['sex_id', 'case_reporter_id',
                        'case_category_id']
        tids = {0: "Case Details"}
        tids[2] = "Case Emergency Details"
        tids[5] = "Other Case Details"
        # Trafficking cases
        tr_case = False
        #  End trafficking
        vals = get_dict(field_name=check_fields)
        case = OVCCaseRecord.objects.get(case_id=case_id)
        person_id = case.person_id
        case_date = case.date_case_opened
        case_categories = OVCCaseCategory.objects.filter(case_id_id=case_id)
        for ccat in case_categories:
            if ccat.case_category in CATS:
                tr_case = True
        initial_info = {'case_narration': case.case_remarks}
        tr_initial_info = {}
        case_infos = get_case_info(request, case_id)
        activities, means, purposes = [], [], []
        for cinfo in case_infos:
            info_type = cinfo.info_type
            if info_type == 'OIEM':
                initial_info['emergency'] = cinfo.info_item
                initial_info['emergency_detail'] = cinfo.info_detail
            elif info_type == 'TACT':
                activities.append(str(cinfo.info_item))
            elif info_type == 'TMNS':
                means.append(str(cinfo.info_item))
            elif info_type == 'TPPS':
                purposes.append(str(cinfo.info_item))
        # Check if in CTiP DB
        ctip_case = get_ctip(request, case_id)
        tr_db = True if ctip_case else False
        is_traffick = 'AYES' if ctip_case else 'ANNO'
        tr_initial_info['ctip_activity'] = activities
        tr_initial_info['ctip_means'] = means
        tr_initial_info['ctip_purpose'] = purposes
        tr_initial_info['is_trafficking'] = is_traffick

        print('init info', initial_info)
        form = CaseInfoForm(initial=initial_info)
        tr_form = CTIPForm(initial=tr_initial_info)
        case_uid = str(case.case_id)
        case_id = case_uid.replace('-', '')
        return render(
            request, 'forms/case_info.html',
            {'case': case, 'vals': vals, 'form': form, 'cats': case_categories,
             'case_uid': case_uid, 'case_id': str(case_id),
             'tr_case': tr_case, 'tr_form': tr_form, 'tr_db': tr_db})
    except Exception as e:
        raise e
    else:
        pass


@login_required
def case_info_form(request, form_id, case_id):
    """Method to save case information."""
    try:
        check_fields = ['sex_id', 'case_reporter_id',
                        'case_category_id']
        tids = {0: "Case Details"}
        tids[1] = "Additional case Information"
        tids[2] = "Emergency cases"
        tids[3] = "Trafficked Persons"
        tids[4] = "Missing Children"
        tids[5] = "Alternative Care"
        tids[6] = "Institution Placements"
        # Trafficking cases
        tr_case = False
        #  End trafficking
        vals = get_dict(field_name=check_fields)
        case = OVCCaseRecord.objects.get(case_id=case_id)
        person_id = case.person_id
        case_date = case.date_case_opened
        case_categories = OVCCaseCategory.objects.filter(case_id_id=case_id)
        for ccat in case_categories:
            if ccat.case_category in CATS:
                tr_case = True
        # Forms
        fid = int(form_id)
        fname = tids[fid] if fid in tids else tids[0]
        if request.method == 'POST':
            if fid == 1:
                case_narration = request.POST.get('case_narration')
                case.case_remarks = case_narration
                case.save(update_fields=["case_remarks"])
            elif fid == 2:
                em = request.POST.get('emergency')
                em_detail = request.POST.get('emergency_detail')
                save_case_info(request, case, 'OIEM', em, em_detail)
            elif fid == 3:
                ctip_params = {}
                ctip_params['case_id'] = case_id
                ctip_params['person_id'] = person_id
                ctip_params['case_date'] = case_date
                handle_ctip(request, 0, ctip_params)
            elif fid == 4:
                pic = handle_photo_upload(request)
                save_photo(request, pic)
            else:
                # Not implemented
                print('nothing to do')
            msg = "%s Info saved successfully" % (fname)
            messages.add_message(request, messages.INFO, msg)
            redirect_url = reverse(case_info, kwargs={'case_id': case_id})
            return HttpResponseRedirect(redirect_url)
        initial_info = {'case_narration': case.case_remarks}
        tr_initial_info = {}
        case_infos = get_case_info(request, case_id)
        # Photos
        photos = get_photo(request, person_id)
        purl = settings.PHOTO_URL
        photo_fs = '/static/img/user-full.png'
        if photos:
            photo_pp = '%s/%s' % (purl, photos.photo_passport.name)
            if photos.photo_fullsize:
                photo_fs = '%s/%s' % (purl, photos.photo_fullsize.name)
        else:
            photo_pp = '/static/img/user-2.jpg'
        print('PP', photo_pp)
        activities, means, purposes = [], [], []
        for cinfo in case_infos:
            info_type = cinfo.info_type
            if info_type == 'OIEM':
                initial_info['emergency'] = cinfo.info_item
                initial_info['emergency_detail'] = cinfo.info_detail
            elif info_type == 'TACT':
                activities.append(str(cinfo.info_item))
            elif info_type == 'TMNS':
                means.append(str(cinfo.info_item))
            elif info_type == 'TPPS':
                purposes.append(str(cinfo.info_item))
        # Check if in CTiP DB
        ctip_case = get_ctip(request, case_id)
        is_traffick = 'AYES' if ctip_case else 'ANNO'
        tr_initial_info['ctip_activity'] = activities
        tr_initial_info['ctip_means'] = means
        tr_initial_info['ctip_purpose'] = purposes
        tr_initial_info['is_trafficking'] = is_traffick

        print('init info', initial_info)
        form = CaseInfoForm(initial=initial_info)
        tr_form = CTIPForm(initial=tr_initial_info)
        case_uid = str(case.case_id)
        case_id = case_uid.replace('-', '')
        templ_name = 'forms/case_info_%s.html' % (str(form_id))
        return render(
            request, templ_name,
            {'case': case, 'vals': vals, 'form': form, 'cats': case_categories,
             'case_uid': case_uid, 'case_id': str(case_id),
             'tr_case': tr_case, 'tr_form': tr_form,
             'form_name': fname, 'photos': photos,
             'photo_pp': photo_pp, 'photo_fs': photo_fs})
    except Exception as e:
        raise e
    else:
        pass


class Myobject(object):
    pass

# ------------------------------------------------------------------------------------
# New additions after upgrade --------------------------------------------------------

@login_required
def list_bursary(request, id):
    """
    Method to do presidential Bursary
    """
    try:
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        person = RegPerson.objects.get(id=id)
        bursaries = OVCGokBursary.objects.filter(person_id=id)
        if request.method == 'POST':
            save_bursary(request, id)
        form = GOKBursaryForm(initial={'person_type': 'TBVC'}, data=request.POST)
        return render(request, 'forms/bursary/list.html',
                      {'status': 200, 'form': form, 'child': person,
                       'vals': vals, 'bursaries': bursaries})
    except Exception as e:
        print('error saving bursary - %s' % (str(e)))
        raise e
    else:
        pass


@login_required
def view_bursary(request, id):
    """
    Method to do presidential Bursary
    """
    try:
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        bursary = OVCGokBursary.objects.get(application_id=id)
        if request.method == 'POST':
            save_bursary(request, id)
        form = GOKBursaryForm(initial={'person_type': 'TBVC'}, data=request.POST)
        return render(request, 'forms/bursary/view.html',
                      {'status': 200, 'form': form,
                       'vals': vals, 'bursary': bursary})
    except Exception as e:
        print('error saving bursary - %s' % (str(e)))
        raise e
    else:
        pass


@login_required
def new_bursary(request, id):
    """
    Method to do presidential Bursary
    """
    try:
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        person = RegPerson.objects.get(id=id)
        if request.method == 'POST':
            save_bursary(request, id)
        form = GOKBursaryForm(initial={'person_type': 'TBVC'}, data=request.POST)
        return render(request, 'forms/bursary/new.html',
                      {'status': 200, 'form': form, 'child': person,
                       'vals': vals})
    except Exception as e:
        print('error saving bursary - %s' % (str(e)))
        raise e
    else:
        pass


@login_required
def edit_bursary(request, id):
    """
    Method to do presidential Bursary
    """
    try:
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        bursary = OVCGokBursary.objects.get(application_id=id)
        bdata = {'fees_amount': bursary.fees_amount,
                 'child_county': bursary.county.area_id}
        if request.method == 'POST':
            save_bursary(request, id)
        form = GOKBursaryForm(initial={'person_type': 'TBVC'}, data=bdata)
        return render(request, 'forms/bursary/edit.html',
                      {'status': 200, 'form': form, 'vals': vals,
                       'bursary': bursary})
    except Exception as e:
        print('error saving bursary - %s' % (str(e)))
        raise e
    else:
        pass


def form_bursary(request, id):
    """
    Method to do presidential Bursary
    """
    try:
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        # Create the HttpResponse object with the appropriate PDF headers.
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="Bursary.pdf"'
        params = {'insurance': 'GOVERNMENT OF KENYA', 'status_id': 1,
                  'insurances': 'BOX 12 Nairobi'}
        resp = create_mcert(response, params)
        return response
    except Exception as e:
        print('error saving bursary - %s' % (str(e)))
        raise e
    else:
        pass

@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_cpara_v1(request, id):
    if request.method == 'POST':
        data = request.POST

        child = RegPerson.objects.get(id=id)
        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
        date_of_event = data.get('d_o_a')
        event = OVCCareEvents.objects.create(
            event_type_id='cpr',
            created_by=request.user.id,
            person=child,
            house_hold=house_hold
        )
        questions = OVCCareQuestions.objects.filter(code__startswith='cp')
        exceptions = ['cp2d', 'cp2q', 'cp74q', 'cp34q', 'cp18q']
        for question in questions:  
            save_cpara_form_by_domain(
                id=id,
                question=question,
                answer=data.get(question.code.lower()),
                house_hold=house_hold,
                caregiver=care_giver,
                event=event,
                date_event=convert_date(date_of_event, fmt='%Y-%m-%d'),
                exceptions=exceptions
            )
        answer_value = {
            'AYES': 1,
            'ANNO': 0,
            0:0
        }

        print(('benchmark_score = ', data.get('bench_array')))
        bench_score = json.loads(data.get('bench_array'))

        # Saving Benchmarks
        OVCCareBenchmarkScore.objects.create(
            household=house_hold,
            benchmark_1=bench_score[0],
            benchmark_2=bench_score[1],
            benchmark_3=bench_score[2],
            benchmark_4=bench_score[3],
            benchmark_5=bench_score[4],
            benchmark_6=bench_score[5],
            benchmark_7=bench_score[6],
            benchmark_8=bench_score[7],
            benchmark_9=bench_score[8],
            benchmark_10=bench_score[9],
            benchmark_11=bench_score[10],
            benchmark_12=bench_score[11],
            benchmark_13=bench_score[12],
            benchmark_14=bench_score[13],
            benchmark_15=bench_score[14],
            benchmark_16=bench_score[15],
            benchmark_17=bench_score[16],
            event=event,
            care_giver=RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id),
        )
        msg = 'Benchmark Assessment save successful'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)
        # get relations
    guardians = RegPersonsGuardians.objects.select_related().filter(
        child_person=id, is_void=False, date_delinked=None)
    siblings = RegPersonsSiblings.objects.select_related().filter(
        child_person=id, is_void=False, date_delinked=None)
    # Reverse relationship
    osiblings = RegPersonsSiblings.objects.select_related().filter(
        sibling_person=id, is_void=False, date_delinked=None)
    oguardians = RegPersonsGuardians.objects.select_related().filter(
        guardian_person=id, is_void=False, date_delinked=None)
    child = RegPerson.objects.get(id=id)
    ovc_id = int(id)
    creg = OVCRegistration.objects.get(is_void=False, person_id=ovc_id)
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

    house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)

    # Get house hold
    hhold = OVCHHMembers.objects.get(is_void=False, person_id=id)
    # Get HH members
    hhid = hhold.house_hold_id
    hhmqs = OVCHHMembers.objects.filter(is_void=False, house_hold_id=hhid).order_by("-hh_head")
    hhmembers2 = hhmqs.exclude(person_id=id)
    hhmembers = hhmembers2.exclude(person=care_giver)
    # Get child geo
    child_geos = RegPersonsGeo.objects.select_related().filter(
        person=child, is_void=False, date_delinked=None)
    all_geos_county, all_geos_wards, all_geos = [], [], []
    for person_geo in child_geos:
        geo_name = str(person_geo.area.area_id)
        geo_type = person_geo.area.area_type_id
        if geo_type == 'GPRV':
            all_geos_county.append(geo_name)
        elif geo_type == 'GDIS':
            all_geos.append(geo_name)
        else:
            all_geos_wards.append(geo_name)
    if all_geos:
        geos = ', '.join(all_geos)
    else:
        geos = None
    if all_geos_wards:
        geo_wards = ', '.join(all_geos_wards)
    else:
        geo_wards = None
    if all_geos_county:
        geo_county = ', '.join(all_geos_county)
    # geo_wards = geo_wards
    if geo_wards is None:
        ward = None
        subcounty = None
        county = None
    else:
        ward_id = int(geo_wards)
        ward = SetupGeography.objects.get(area_id=ward_id)
        subcounty = SetupGeography.objects.get(area_id=ward.parent_area_id)
        county = SetupGeography.objects.get(area_id=subcounty.parent_area_id)

    # orgunit = RegPersonsOrgUnits.objects.get(person=child)
    form = CparaAssessment_v1()
    ovc_id = int(id)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

    # PAST CPARA
    past_cpara = []
    cpara_events = OVCCareEvents.objects.filter(event_type_id='cpr', person_id=child.id)
    if cpara_events:
        for one_cpara_event in cpara_events:
            event_detail = ""
            total_benchmark_score = 0
            # cpara_data = OVCCareCpara.objects.filter(event=one_cpara_event)
            cpara_data = OVCCareBenchmarkScore.objects.filter(event_id=one_cpara_event.event)
            bm_array = []
            if cpara_data:
                for one_cpara_bench in cpara_data:
                    bm_array.append("Yes" if one_cpara_bench.benchmark_1 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_2 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_3 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_4 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_5 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_6 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_7 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_8 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_9 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_10 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_11 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_12 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_13 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_14 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_15 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_16 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_17 == 1 else "No")
                    benchmark_1 = "Benchmark 1: (Yes)" if one_cpara_bench.benchmark_1 == 1 else "Benchmark 1: (No)"
                    benchmark_2 = "Benchmark 2: (Yes)" if one_cpara_bench.benchmark_2 == 1 else "Benchmark 2: (No)"
                    benchmark_3 = "Benchmark 3: (Yes)" if one_cpara_bench.benchmark_3 == 1 else "Benchmark 3: (No)"
                    benchmark_4 = "Benchmark 4: (Yes)" if one_cpara_bench.benchmark_4 == 1 else "Benchmark 4: (No)"
                    benchmark_5 = "Benchmark 5: (Yes)" if one_cpara_bench.benchmark_5 == 1 else "Benchmark 5: (No)"
                    benchmark_6 = "Benchmark 6: (Yes)" if one_cpara_bench.benchmark_6 == 1 else "Benchmark 6: (No)"
                    benchmark_7 = "Benchmark 7: (Yes)" if one_cpara_bench.benchmark_7 == 1 else "Benchmark 7: (No)"
                    benchmark_8 = "Benchmark 8: (Yes)" if one_cpara_bench.benchmark_8 == 1 else "Benchmark 8: (No)"
                    benchmark_9 = "Benchmark 9: (Yes)" if one_cpara_bench.benchmark_9 == 1 else "Benchmark 9: (No)"
                    benchmark_10 = "Benchmark 10: (Yes)" if one_cpara_bench.benchmark_10 == 1 else "Benchmark 10: (No)"
                    benchmark_11 = "Benchmark 11: (Yes)" if one_cpara_bench.benchmark_11 == 1 else "Benchmark 11: (No)"
                    benchmark_12 = "Benchmark 12: (Yes)" if one_cpara_bench.benchmark_12 == 1 else "Benchmark 12: (No)"
                    benchmark_13 = "Benchmark 13: (Yes)" if one_cpara_bench.benchmark_13 == 1 else "Benchmark 13: (No)"
                    benchmark_14 = "Benchmark 14: (Yes)" if one_cpara_bench.benchmark_14 == 1 else "Benchmark 14: (No)"
                    benchmark_15 = "Benchmark 15: (Yes)" if one_cpara_bench.benchmark_15 == 1 else "Benchmark 15: (No)"
                    benchmark_16 = "Benchmark 16: (Yes)" if one_cpara_bench.benchmark_16 == 1 else "Benchmark 16: (No)"
                    benchmark_17 = "Benchmark 17: (Yes)" if one_cpara_bench.benchmark_17 == 1 else "Benchmark 17: (No)"

                    str_1 = benchmark_1 + ", " + benchmark_2 + ", " + benchmark_3 + ", " + benchmark_4 + ", " + benchmark_5 + ", "
                    str_2 = benchmark_6 + ", " + benchmark_7 + ", " + benchmark_8 + ", " + benchmark_9 + ", "
                    str_3 = benchmark_10 + ", " + benchmark_11 + ", " + benchmark_12 + ", " + benchmark_13 + ", "
                    str_4 = benchmark_14 + ", " + benchmark_15 + ", " + benchmark_16 + ", " + benchmark_17

                    total_benchmark_score = int(one_cpara_bench.benchmark_1) + int(one_cpara_bench.benchmark_2) + int(
                        one_cpara_bench.benchmark_3) + int(one_cpara_bench.benchmark_4) + int(
                        one_cpara_bench.benchmark_5) + int(one_cpara_bench.benchmark_6) + int(
                        one_cpara_bench.benchmark_7) + int(one_cpara_bench.benchmark_8) + int(
                        one_cpara_bench.benchmark_9) + int(one_cpara_bench.benchmark_10) + int(
                        one_cpara_bench.benchmark_11) + int(one_cpara_bench.benchmark_12) + int(
                        one_cpara_bench.benchmark_13) + int(one_cpara_bench.benchmark_14) + int(
                        one_cpara_bench.benchmark_15) + int(one_cpara_bench.benchmark_16) + int(
                        one_cpara_bench.benchmark_17)
                    full_str = str_1 + str_2 + str_3 + str_4
                    # qn_string = str(one_cpara_bench.question_code) + " (" + str(one_cpara_bench.answer) + "), "
                    event_detail = event_detail + full_str
            else:
                event_detail = "No answered questions found"
                total_benchmark_score = 0
                # cpara_data = OVCCareCpara.objects.filter(event=one_cpara_event)
                cpara_data = OVCCareBenchmarkScore.objects.filter(event_id=one_cpara_event.event)
                bm_array = []
            past_cpara.append({
                'ev_date': one_cpara_event.date_of_event,
                'ev_person': child.id,
                'ev_type': 'CPARA',
                'ev_id': str(one_cpara_event.pk),
                'ev_detail': str(event_detail),
                'ev_score': total_benchmark_score,
                'bm_array': bm_array
            })

    return render(request,
                  'forms/new_cpara_v1.html',
                  {
                      'form': form,
                      'person': id,
                      'siblings': siblings,
                      'hhmembers': hhmembers,
                      'osiblings': osiblings,
                      'oguardians': oguardians,
                      'child': child,
                      'creg': creg,
                      'caregiver': care_giver,
                      'household': house_hold,
                      'ward': ward,
                      'subcounty': subcounty,
                      'county': county,
                      'care_giver': care_giver,
                      'past_cpara': past_cpara
                      #   'orgunit' : orgunit,

                  })


@login_required(login_url='/')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_cpara_v1(request, id, btn_event_pk):
    jsonCPARAData = []
    msg = ''
    try:
        event_id = uuid.UUID(btn_event_pk)
        d_event = OVCCareEvents.objects.filter(pk=event_id)[0].timestamp_created
        delta = get_days_difference(d_event)
        if delta < 90:
            event = OVCCareEvents.objects.filter(pk=event_id)
            if event:
                # delete cpara
                ovcpara = OVCCareCpara.objects.filter(event=event)
                if ovcpara:
                    ovcpara.delete()
                    msg = "Deleted successfully"
                # delete event
                event.delete()
                msg = "Deleted successfully"
        else:
            msg = "Can't delete after 90 days"
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
    jsonCPARAData.append({'msg': msg})
    return JsonResponse(jsonCPARAData,
                        content_type='application/json',
                        safe=False)

from .models import OVCCareCasePlan


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def case_plan_template(request, id):
    if request.method == 'POST':
        child = RegPerson.objects.get(id=id)
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
        event_type_id = 'CPAR'

        """ Save caseplan-event """
        # get event counter
        event_counter = OVCCareEvents.objects.filter(
            event_type_id=event_type_id, person=id, is_void=False).count()
        # save event
        ovccareevent = OVCCareEvents.objects.create(
            event_type_id=event_type_id,
            event_counter=event_counter,
            event_score=0,
            created_by=request.user.id,
            person=RegPerson.objects.get(pk=int(id)),
            house_hold=house_hold
        )

        my_request = request.POST.get('final_submission')

        # house_hold=
        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
        caregiver_id = OVCRegistration.objects.get(person=child).caretaker_id

        if my_request:
            caseplandata = json.loads(my_request)
            for all_data in caseplandata:
                my_domain = all_data['domain']
                my_goal = all_data['goal']
                my_gap = all_data['gaps']
                my_action = all_data['actions']
                my_service = all_data['services']
                my_responsible = all_data['responsible']
                my_actual_completion_date = all_data['actual_completion_date']
                my_date_completed = all_data['date']
                my_date_of_prev_evnt = timezone.now()
                my_date_of_caseplan = all_data['CPT_DATE_CASEPLAN']
                my_results = all_data['results']
                my_reason = all_data['reasons']
                print(("my_reason", all_data))

                xyz = RegPerson.objects.filter(id=caregiver_id).values('id')

                for service in my_service:
                    OVCCareCasePlan(
                        domain=my_domain,
                        goal=my_goal,
                        person_id=id,
                        caregiver=RegPerson.objects.get(id=caregiver_id),
                        household=house_hold,
                        need=my_gap,
                        priority=my_action,
                        # cp_service = SetupList.objects.get(item_id = service),
                        cp_service=service,
                        responsible=my_responsible,
                        date_of_previous_event=my_date_of_prev_evnt,
                        date_of_event=convert_date(my_date_of_caseplan, fmt='%Y-%m-%d'),
                        form=OVCCareForms.objects.get(name='OVCCareCasePlan'),
                        completion_date=convert_date(my_date_completed, fmt='%Y-%m-%d'),
                        actual_completion_date=convert_date(my_actual_completion_date, fmt='%Y-%m-%d'),
                        results=my_results,
                        reasons=my_reason,
                        case_plan_status='D',
                        event=ovccareevent
                    ).save()

        msg = 'Case Plan saved successfully'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)

    # get child data
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id', 'relationship_type_id']
    vals = get_dict(field_name=check_fields)
    ovc_id = int(id)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(
        id=OVCRegistration.objects.get(person=child).caretaker_id)
    form = CasePlanTemplate()

    # past cpt
    caseplan_events = get_past_cpt(child.id)

    return render(request,
                  'forms/case_plan_template.html',
                  {'form': form, 'init_data': init_data,
                   'vals': vals, 'child': child,
                   'caseplan_events': caseplan_events,
                   'care_giver': care_giver})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def update_caseplan(request, event_id, ovcid):
    this_eventt = OVCCareEvents.objects.get(event_type_id='CPAR', pk=event_id)
    this_event_pk = this_eventt.event
    child = RegPerson.objects.get(id=ovcid)

    if request.method == 'POST':
        d_event = OVCCareEvents.objects.filter(pk=event_id)[0].timestamp_created
        delta = get_days_difference(d_event)

        if delta < 90:
            try:
                my_request = request.POST.get('final_submission')

                child = RegPerson.objects.get(id=ovcid)
                house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)

                care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
                caregiver_id = OVCRegistration.objects.get(person=child).caretaker_id

                if my_request:
                    caseplandata = json.loads(my_request)
                    for all_data in caseplandata:
                        acd = all_data['actual_completion_date'] if 'actual_completion_date' in all_data else '1900-01-01'
                        my_domain = all_data['domain']
                        my_goal = all_data['goal']
                        my_gap = all_data['gaps']
                        my_action = all_data['actions']
                        my_service = all_data['services']
                        my_responsible = all_data['responsible']
                        my_date_completed = all_data['date']
                        my_actual_completion_date = acd
                        my_date_of_prev_evnt = timezone.now()
                        my_date_of_caseplan = all_data['CPT_DATE_CASEPLAN']
                        my_results = all_data['results']
                        my_reason = all_data['reasons']

                    xyz = RegPerson.objects.filter(id=caregiver_id).values('id')

                    for service in my_service:
                        print(('person_id', id))
                        print(('person_ovcid', ovcid))
                        print(('caregiver_id', caregiver_id))
                        OVCCareCasePlan(
                            domain=my_domain,
                            goal=my_goal,
                            person_id=ovcid,
                            caregiver_id=caregiver_id,
                            household=house_hold,
                            need=my_gap,
                            priority=my_action,
                            cp_service=service,
                            responsible=my_responsible,
                            date_of_previous_event=my_date_of_prev_evnt,
                            date_of_event=convert_date(my_date_of_caseplan, fmt='%Y-%m-%d'),
                            form=OVCCareForms.objects.get(name='OVCCareCasePlan'),
                            completion_date=convert_date(my_date_completed, fmt='%Y-%m-%d'),
                            actual_completion_date=convert_date(my_actual_completion_date, fmt='%Y-%m-%d'),
                            results=my_results,
                            reasons=my_reason,
                            case_plan_status='D',
                            event_id=this_event_pk
                        ).save()

                msg = 'Case Plan updated successfully'
                messages.add_message(request, messages.INFO, msg)
                url = reverse('ovc_view', kwargs={'id': ovcid})
                return HttpResponseRedirect(url)
            except Exception as e:
                print('error updating caseplan - %s' % (str(e)))
                return False
        else:
            msg = "Can't update after 30 days"
            messages.add_message(request, messages.ERROR, msg)
            url = reverse('ovc_view', kwargs={'id': ovcid})
            return HttpResponseRedirect(url)
    form = CasePlanTemplate()
    ovc_id = int(ovcid)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(
        id=OVCRegistration.objects.get(person=child).caretaker_id)
    caseplan_events = get_past_cpt(ovc_id)

    check_fields = ['sex_id', 'relationship_type_id']
    vals = get_dict(field_name=check_fields)
    init_data = RegPerson.objects.filter(pk=ovcid)

    return render(request, 'forms/update_cpt.html',
                  {'form': form, 'init_data': init_data, 'vals': vals,
                   'child': child, 'this_event': this_eventt,
                   'care_giver': care_giver,
                   'caseplan_events': caseplan_events})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def monitor_caseplan(request, event_id, ovcid):
    this_eventt = OVCCareEvents.objects.get(event_type_id='CPAR', pk=event_id)
    this_event_pk = this_eventt.event
    child = RegPerson.objects.get(id=ovcid)

    if request.method == 'POST':
        d_event = OVCCareEvents.objects.filter(
            pk=event_id)[0].timestamp_created
        delta = get_days_difference(d_event)
        if delta < 90:
            try:
                cp_item_id = request.POST.get('item_id')
                cpta_date = request.POST.get('CPT_ACTUAL_DATE_COMPLETION')
                cp_results = request.POST.get('CPT_RESULTS')
                cp_reasons = request.POST.get('CPT_REASONS')
                cp_actual_date = convert_date(cpta_date)
                case_plan = OVCCareCasePlan.objects.get(pk=cp_item_id)
                case_plan.results = cp_results
                case_plan.reasons = cp_reasons
                case_plan.actual_completion_date = cp_actual_date
                case_plan.case_plan_status = 'M'
                case_plan.save()
                status = 0
                msg = 'Case Plan monitoring saved successfully'
            except Exception as e:
                status = 9
                msg = 'Error updating case plan - %s' % (e)
        else:
            status = 1
            msg = "Can't update after 30 days"
        messages.add_message(request, messages.INFO, msg)
        return JsonResponse({'message': msg, 'status': status})

    # Default GET
    form = CasePlanTemplate()
    ovc_id = int(ovcid)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(
        id=OVCRegistration.objects.get(person=child).caretaker_id)
    caseplan_events = get_past_cpt(ovc_id)

    check_fields = ['sex_id', 'relationship_type_id', 'case_plan_goals_health',
                    'case_plan_goals_school', 'case_plan_goals_stable',
                    'case_plan_goals_safe', 'case_plan_gaps_health',
                    'case_plan_gaps_school', 'case_plan_gaps_stable',
                    'case_plan_gaps_safe', 'case_plan_priorities_health',
                    'case_plan_priorities_school',
                    'case_plan_priorities_stable',
                    'case_plan_priorities_safe', 'case_plan_services_health',
                    'case_plan_services_school', 'case_plan_services_stable',
                    'case_plan_services_safe']
    vals = get_dict(field_name=check_fields)
    init_data = RegPerson.objects.filter(pk=ovcid)

    return render(request, 'forms/monitor_case_plan.html',
                  {'form': form, 'init_data': init_data, 'vals': vals,
                   'child': child, 'this_event': this_eventt,
                   'care_giver': care_giver, 'cp_id': event_id,
                   'caseplan_events': caseplan_events})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_caseplan(request, id, event_id):
    try:
        this_event = OVCCareEvents.objects.get(
            event_type_id='CPAR', pk=event_id)
        event_id = this_event.event
        # Soft delete case plans - is_void = True
        OVCCareCasePlan.objects.filter(event_id=event_id).update(is_void=True)
        this_event.is_void = True
        this_event.save()
        # Redirect
        msg = 'Case Plan deleted successfully'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)
    except Exception as e:
        raise e
    else:
        pass


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_case_plan_monitoring(request, id):
    if request.method == 'POST':
        data = request.POST
        child = RegPerson.objects.get(id=id)
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
        event = OVCCareEvents.objects.create(
            event_type_id='cpr',
            created_by=request.user.id,
            person=child,
            house_hold=house_hold
        )
        event_date = convert_date(data.get('cm1d'))
        month = event_date.month
        quarter = 0
        if month in [10, 11, 12]:
            quarter = 1
        elif month in [1, 2, 3]:
            quarter = 2
        elif month in [4, 5, 6]:
            quarter = 3
        elif month in [7, 8, 9]:
            quarter = 4
        answer_value = {
            'AYES': 'Yes',
            'ANNO': 'No'
        }
        try:
            OVCMonitoring.objects.create(
                household=house_hold,
                hiv_status_knowledge=answer_value[data.get('cm2q')],
                viral_suppression=answer_value[data.get('cm3q')],
                hiv_prevention=answer_value[data.get('cm4q')],
                undernourished=answer_value[data.get('cm5q')],
                access_money=answer_value[data.get('cm6q')],
                violence=answer_value[data.get('cm7q')],
                caregiver=answer_value[data.get('cm8q')],
                school_attendance=answer_value[data.get('cm9q')],
                school_progression=answer_value[data.get('cm10q')],
                cp_achievement=answer_value[data.get('cm11q')],
                case_closure=answer_value[data.get('cm12q')],
                case_closure_checked=data.get('cm13q'),
                quarter=quarter,
                event=event,
                event_date=event_date
            )
        except Exception as e:
            print('error saving caseplan monitoring - %s' % (str(e)))
            return False
        msg = 'Case Plan Monitoring saved successful'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)
    else:
        form = CparaMonitoring()

        ovc_id = int(id)
        child = RegPerson.objects.get(is_void=False, id=ovc_id)
        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

        # Show previous cpara monitoring events
        event = OVCCareEvents.objects.filter(person_id=ovc_id).values_list('event')
        cpara_mon_data = OVCMonitoring.objects.filter(event_id__in=event).order_by('event_date')

        return render(request, 'forms/new_case_plan_monitoring.html',
                      {'form': form, 'care_giver': care_giver,
                       'cpara_mon_data': cpara_mon_data,
                       'child': child})


def fetch_question(answer_item_code):
    question_code = answer_item_code
    OVCCareQuestions.objects.get(pk=question_code)
    return question_code


def persist_wellbeing_data(kvals, value, person, house_hold, new_pk, date_of_wellbeing_event, request, id):
    question_code_to_ui_item_mapping = {
        'WB_GEN_07': 'WB_GEN_06', "WB_GEN_08": "WB_GEN_07", "WB_GEN_09": "WB_GEN_07",
        "WB_SAF_32_1": "WB_SAF_31", "WB_SAF_33_1": "WB_SAF_32", "WB_SAF_34_2": "WB_SAF_33", "WB_SAF_34_1": "WB_SAF_33",
        "WB_SAF_35_1": "WB_SAF_34", "WB_SAF_36_1": "WB_SAF_35", "WB_SAF_36_2": "WB_SAF_35",
        "WB_GEN_02": "WB_GEN_02", "WB_GEN_03": "WB_GEN_03", "WB_GEN_01": "WB_GEN_01",
        "WB_SAF_37_1": "WB_SAF_36", "WB_SAF_37_2": "WB_SAF_36", "WB_SAF_39_1": "WB_SAF_37", "WB_SAF_39_2": "WB_SAF_37",
        "WB_SAF_40_1": "WB_SAF_38", "WB_SAF_40_2": "WB_SAF_38", "WB_SCH_39_1": "WB_SCH_39", "WB_SCH_39_1": "WB_SCH_39",
        "WB_SCH_40_1": "WB_SCH_40", "WB_SCH_41_1": "WB_SCH_41", "WB_SCH_41_2": "WB_SCH_41",
        "WB_SCH_42_2": "WB_SCH_42", "WB_SCH_42_1": "WB_SCH_42", "WB_SCH_44_1": "WB_SCH_44",
        "WB_SCH_45_1": "WB_SCH_46", "WB_HEL_14_1": "WB_HEL_14", "WB_HEL_14_2": "WB_HEL_14", "WB_HEL_15_1": "WB_HEL_15",
        "WB_HEL_16_1": "WB_HEL_16", "WB_HEL_16_2": "WB_HEL_17", "WB_HEL_16_3": "WB_HEL_17", "WB_HEL_16_4": "WB_HEL_18",
        "WB_HEL_16_5": "WB_HEL_20",
        "WB_HEL_17_1": "WB_HEL_19", "WB_HEL_18_1": "WB_HEL_20", "WB_HEL_18_2": "WB_HEL_17", "WB_HEL_19_1": "WB_HEL_21",
        "WB_HEL_20_2": "WB_HEL_22", "WB_HEL_20_1": "WB_HEL_22", "WB_HEL_21_1": "WB_HEL_23", "WB_HEL_22_1": "WB_HEL_24",
        "WB_HEL_23_1": "WB_HEL_25", "WB_HEL_24_1": "WB_HEL_26", "WB_HEL_25_1": "WB_HEL_27", "WB_HEL_25_2": "WB_HEL_27",
        "WB_HEL_26_1": "WB_HEL_28", "WB_HEL_27_1": "WB_HEL_29", "WB_HEL_27_2": "WB_HEL_29", "WB_HEL_28_1": "WB_HEL_30",
        "WB_HEL_28_2": "WB_HEL_30",
        "WB_STA_1_1": "WB_STA_1", "WB_STA_1_2": "WB_STA_1", "WB_STA_1_3": "WB_STA_1", "WB_STA_2_1": "WB_STA_2",
        "WB_STA_2_2": "WB_STA_2", "WB_STA_2_3": "WB_STA_2",
        "WB_STA_3_1": "WB_STA_3", "WB_STA_3_2": "WB_STA_3", "WB_STA_3_3": "WB_STA_3", "WB_STA_4_1": "WB_STA_4",
        "WB_STA_4_2": "WB_STA_4", "WB_STA_4_3": "WB_STA_4",
        "WB_STA_5_1": "WB_STA_5", "WB_STA_5_2": "WB_STA_5", "WB_STA_5_3": "WB_STA_5", "WB_STA_6_1": "WB_STA_6",
        "WB_STA_7_1": "WB_STA_7", "WB_STA_8_1": "WB_STA_8", "WB_STA_8_2": "WB_STA_8", "WB_STA_9_1": "WB_STA_9",
        "WB_STA_9_2": "WB_STA_9",
        "WB_STA_10_1": "WB_STA_10", "WB_STA_10_2": "WB_STA_10", "WB_STA_11_1": "WB_STA_11", "WB_STA_11_2": "WB_STA_11",
        "WB_STA_12_1": "WB_STA_12", "WB_STA_12_2": "WB_STA_12", "WB_STA_12_3": "WB_STA_12", "WB_STA_13_1": "WB_STA_13",
        "WB_STA_13_2": "WB_STA_13",
        "WB_GEN_04": "WB_GEN_04", "WB_GEN_05": "WB_GEN_05", "WB_GEN_07": "WB_GEN_06", "WB_GEN_06": "WB_GEN_06",
        "WB_GEN_08": "WB_GEN_07", "WB_GEN_09": "WB_GEN_07", 'WB_GEN_12': 'WB_GEN_01', 'WB_GEN_04': 'WB_GEN_04',
        'WB_GEN_05': 'WB_GEN_05'
    }

    other_list = ['WB_SAF_1_2', 'WB_SAF_31_2', 'WB_SAF_34_2', 'WB_SAF_37_2', 'WB_SAF_38_2', 'WB_SAF_39_2', 'WB_SAF_40_2'
        , 'WB_SCH_41_2', 'WB_STA_1_2', 'WB_STA_2_2', 'WB_STA_3_2',
                  'WB_STA_4_2', 'WB_STA_5_2', 'WB_STA_5_3', 'WB_STA_8_2', 'WB_STA_9_2', 'WB_HEL_25_2', 'WB_HEL_27_2',
                  'WB_HEL_28_2', 'WB_HEL_14_2', 'WB_HEL_20_2']

    entity = kvals["entity"]
    question_code = kvals["question_code"]
    demographics_items = ['WB_GEN_12', 'WB_GEN_13', 'WB_GEN_15', 'WB_GEN_06', 'WB_GEN_08']
    # try:
    question_code = question_code_to_ui_item_mapping[question_code]
    ovc_qst = OVCCareQuestions.objects.get(question=question_code)

    if (entity == 'wellbeing' and kvals["question_code"] not in demographics_items):
        OVCCareWellbeing(
            question_code=ovc_qst.code,
            person=person,
            question=ovc_qst,
            answer=value,
            household=house_hold,
            question_type='CG',
            domain=ovc_qst.domain,
            date_of_event=date_of_wellbeing_event,
            event=OVCCareEvents.objects.get(pk=new_pk)
            # caregiver=id
        ).save()

    if (entity == 'comment' or kvals["question_code"] in other_list):
        explanation_uuid = uuid.UUID('3249b14e-3e83-11e9-b210-d663bd873d93')
        ovc_Care_forms_obj = OVCCareForms.objects.get(pk=explanation_uuid)
        OVCExplanations(
            question=ovc_qst,
            comment=value,
            form=ovc_Care_forms_obj,
            event=OVCCareEvents.objects.get(pk=new_pk)
        ).save()

    # except Exception, e:
    #     print "error saving wellbeing data"
    #     print e

    if (kvals["question_code"] in demographics_items):
        m_value = 0
        f_value = 0
        key = ''

        if (kvals["question_code"] == 'WB_GEN_12'):
            status_val = {'Monogamous Marriage': '1', 'Polygamous Marriage': '2', 'Single': '3', 'Widowed': '4',
                          'Divorced': '5', 'Cohabiting': '6'}
            m_value = status_val[value]
            f_value = status_val[value]
            key = 'MARS'

        if (kvals["question_code"] == 'WB_GEN_13'):
            m_value = request.POST.get('WB_GEN_13')  # male
            f_value = request.POST.get('WB_GEN_14')  # female
            key = 'IU18'

        if (kvals["question_code"] == 'WB_GEN_15'):
            m_value = request.POST.get('WB_GEN_15')  # male
            f_value = request.POST.get('WB_GEN_16')  # female
            key = 'DU18'

        if (kvals["question_code"] == 'WB_GEN_06'):
            m_value = request.POST.get('WB_GEN_06')  # male
            f_value = request.POST.get('WB_GEN_07')  # female
            key = 'IO18'

        if (kvals["question_code"] == 'WB_GEN_08'):
            m_value = request.POST.get('WB_GEN_08')  # male
            f_value = request.POST.get('WB_GEN_09')  # female
            key = 'DO18'

        OVCHouseholdDemographics(
            household=house_hold,
            key=key,
            male=m_value,
            female=f_value,
            event=OVCCareEvents.objects.get(pk=new_pk)
        ).save()
        msg = 'wellbeing saved successful'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)


def persist_per_child_wellbeing_question(request, key, house_hold, new_events_pk):
    date_of_wellbeing_event = convert_date(request.POST.get('WB_GEN_01'))
    if (key == 'safeanswer'):
        answer_obj = request.POST.get(key)
        answer_obj = ast.literal_eval(answer_obj)  # convert to dict
        for person_id, individual_person_answers in answer_obj.items():
            # individual_person_answers=ast.literal_eval(individual_person_answers)
            person = RegPerson.objects.get(pk=int(person_id))
            for element_id, answer in individual_person_answers.items():
                kvals = {"entity": "wellbeing", "value": answer, "question_code": element_id}
                persist_wellbeing_data(kvals, answer, person, house_hold, new_events_pk, date_of_wellbeing_event,
                                       request, id)

    if (key == 'schooledanswer'):
        answer_obj = request.POST.get(key)
        answer_obj = ast.literal_eval(answer_obj)  # convert to dict
        for person_id, individual_person_answers in answer_obj.items():
            # individual_person_answers=ast.literal_eval(individual_person_answers)
            person = RegPerson.objects.get(pk=int(person_id))
            for element_id, answer in individual_person_answers.items():

                kvals = {"entity": "wellbeing", "value": answer, "question_code": element_id}
                if isinstance(answer, list):
                    for vall in answer:
                        kvals['value'] = vall
                        persist_wellbeing_data(kvals, vall, person, house_hold, new_events_pk, date_of_wellbeing_event,
                                               request, id)
                else:
                    persist_wellbeing_data(kvals, answer, person, house_hold, new_events_pk, date_of_wellbeing_event,
                                           request)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_wellbeing(request, id):
    # try:

    if request.method == 'POST':
        comments = ['WB_STA_13_2', 'WB_STA_12_3', 'WB_STA_11_2', 'WB_STA_10_2', 'WB_STA_5_3', 'WB_STA_4_3',
                    'WB_STA_3_3', 'WB_STA_2_3', 'WB_STA_1_3']

        ignore_request_values = ['household_id', 'csrfmiddlewaretoken']

        household_id = request.POST.get('household_id')
        caretker_id = request.POST.get('caretaker_id')

        hse_uuid = uuid.UUID(household_id)
        house_hold = OVCHouseHold.objects.get(pk=hse_uuid)
        person = RegPerson.objects.get(pk=int(caretker_id))
        event_type_id = 'WBG'
        date_of_wellbeing_event = convert_date(request.POST.get('WB_GEN_01'), fmt='%Y-%m-%d')

        """ Save Wellbeing-event """
        event_counter = OVCCareEvents.objects.filter(
            event_type_id=event_type_id, person=id, is_void=False).count()
        print("save event")
        ovccareevent = OVCCareEvents(
            event_type_id=event_type_id,
            event_counter=event_counter,
            event_score=0,
            date_of_event=date_of_wellbeing_event,
            created_by=request.user.id,
            person=RegPerson.objects.get(pk=int(id)),
            house_hold=house_hold
        )
        ovccareevent.save()
        new_events_pk = ovccareevent.pk
        ovc_id = int(id)
        child = RegPerson.objects.get(is_void=False, id=ovc_id)
        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
        print(('ssssssssss', care_giver))

        entity_values = []
        for key in request.POST:
            if (str(key) != "safeanswer" and str(key) != "schooledanswer" and "WB_SCH_39" not in str(
                    key) and "WB_SCH_40" not in str(key) and "WB_SCH_41" not in str(key) and "WB_SCH_42" not in str(
                key) and "WB_SAF_31_1" not in str(key) and "WB_SCH_43" not in str(key) and "WB_SCH_44" not in str(
                key) and "WB_SCH_45" not in str(key) and "WB_SAF_37" not in str(key) and "WB_SAF_38" not in str(
                key) and "WB_SAF_39" not in str(key) and "WB_SAF_40" not in str(key) and "WB_HEL_17_2" not in str(
                key) and "WB_GEN_11" not in str(key) and "WB_GEN_13" not in str(key) and "WB_GEN_15" not in str(
                key) and "WB_GEN_14" not in str(key) and "WB_GEN_16" not in str(key) and "caretaker_id" not in str(
                key)):

                if (key in ignore_request_values):
                    continue
                val = request.POST.getlist(key)
                for i, value in enumerate(val):
                    entity_type = 'wellbeing'
                    if (key in comments):
                        entity_type = 'comment'
                    kvals = {"entity": entity_type, "value": val, "question_code": key,
                             'domain': 1}
                    persist_wellbeing_data(kvals, value, person, house_hold, new_events_pk, date_of_wellbeing_event,
                                           request, id)
            else:
                persist_per_child_wellbeing_question(request, key, house_hold, new_events_pk)
        url = reverse('ovc_view', kwargs={'id': id})

        # return HttpResponseRedirect(reverse(forms_registry))
        return HttpResponseRedirect(url)
    # except Exception, e:
    #     msg = 'wellbeing save error: (%s)' % (str(e))
    #     messages.add_message(request, messages.ERROR, msg)
    #     print 'Error saving wellbeing : %s' % str(e)
    #     print e
    #     return HttpResponseRedirect(reverse(forms_registry))

    # get household members/ caretaker/ household_id
    household_id = None
    ovcreg = None
    person_sex_type = 'male'
    try:
        ovcreg = get_object_or_404(OVCRegistration, person_id=id, is_void=False)

        person_sex_type = 'male' if ovcreg.caretaker.sex_id == 'SMAL' else 'female'
        caretaker_id = ovcreg.caretaker_id if ovcreg else None
        ovchh = get_object_or_404(OVCHouseHold, head_person=caretaker_id, is_void=False)
        household_id = ovchh.id if ovchh else None
    except Exception as e:
        print(str(e))
        msg = 'Error getting household identifier: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))

        # get relations
    guardians = RegPersonsGuardians.objects.select_related().filter(
        child_person=id, is_void=False, date_delinked=None)
    # siblings = RegPersonsSiblings.objects.select_related().filter(
    #     child_person=id, is_void=False, date_delinked=None)
    ovc_id = int(id)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)

    siblings = RegPersonsSiblings.objects.filter(
        is_void=False, child_person=child.id)

    # Reverse relationship
    osiblings = RegPersonsSiblings.objects.select_related().filter(
        sibling_person=id, is_void=False, date_delinked=None)

    oguardians = RegPersonsGuardians.objects.select_related().filter(
        guardian_person=id, is_void=False, date_delinked=None)

    # get child data
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id', 'relationship_type_id']
    vals = get_dict(field_name=check_fields)

    # Get house hold
    hhold = OVCHHMembers.objects.get(
        is_void=False, person_id=child.id)
    # Get HH members
    hhid = hhold.house_hold_id
    hhmqs = OVCHHMembers.objects.filter(
        is_void=False, house_hold_id=hhid).order_by("-hh_head")

    hhmembers = hhmqs.exclude(person_id=ovcreg.caretaker_id)
    # Get child geo
    child_geos = RegPersonsGeo.objects.select_related().filter(
        person=child, is_void=False, date_delinked=None)
    all_geos_county, all_geos_wards, all_geos = [], [], []
    for person_geo in child_geos:
        geo_name = str(person_geo.area.area_id)
        geo_type = person_geo.area.area_type_id
        if geo_type == 'GPRV':
            all_geos_county.append(geo_name)
        elif geo_type == 'GDIS':
            all_geos.append(geo_name)
        else:
            all_geos_wards.append(geo_name)
    if all_geos:
        geos = ', '.join(all_geos)
    if all_geos_wards:
        geo_wards = ', '.join(all_geos_wards)
    if all_geos_county:
        geo_county = ', '.join(all_geos_county)
    if geo_wards is None:
        ward = None
        subcounty = None
        county = None
    else:
        ward_id = int(geo_wards)
        ward = SetupGeography.objects.get(area_id=ward_id)
        subcounty = SetupGeography.objects.get(area_id=ward.parent_area_id)
        county = SetupGeography.objects.get(area_id=subcounty.parent_area_id)

    form = Wellbeing(initial={'household_id': household_id, 'caretaker_id': caretaker_id, })
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

    return render(request,
                  'forms/new_wellbeing.html',
                  {
                      'form': form,
                      'init_data': init_data,
                      'vals': vals,
                      'ovcreg': ovcreg,
                      'person': id,
                      'guardians': guardians,
                      'siblings': siblings,
                      'hhmembers': hhmembers,
                      'osiblings': osiblings,

                      'person_sex_type': person_sex_type,
                      'oguardians': oguardians,

                      'county': county,
                      'ward': ward,
                      'subcounty': subcounty,
                      'care_giver': care_giver
                  })


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_wellbeingadolescent(request, id):
    try:
        if request.method == 'POST':
            comments = ['WB_AD_GEN_4_2']
            ignore_request_values = ['household_id', 'csrfmiddlewaretoken']

            household_id = request.POST.get('household_id')
            hse_uuid = uuid.UUID(household_id)
            house_holds = OVCHouseHold.objects.get(pk=hse_uuid)
            person = RegPerson.objects.get(pk=int(id))
            event_type_id = 'WBGA'
            date_of_wellbeing_event = timezone.now()

            """ Save Wellbeing-event """
            # get event counter
            event_counter = OVCCareEvents.objects.filter(
                event_type_id=event_type_id, person=id, is_void=False).count()
            # save event
            ovccareevent = OVCCareEvents(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                date_of_event=date_of_wellbeing_event,
                created_by=request.user.id,
                person=RegPerson.objects.get(pk=int(id)),
                house_hold=house_holds
            )
            ovccareevent.save()
            # get questions for adolescent
            questions = OVCCareQuestions.objects.filter(code__startswith='wba')
            ovc_id = int(id)
            child = RegPerson.objects.get(is_void=False, id=ovc_id)
            care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
            for question in questions:
                answer = request.POST.get(question.question)
                if answer is None:
                    answer = 'No'
                OVCCareWellbeing.objects.create(
                    person=RegPerson.objects.get(pk=int(id)),
                    question=question,
                    answer=answer,
                    household=house_holds,
                    event=ovccareevent,
                    date_of_event=timezone.now(),
                    domain=question.domain,
                    question_type=question.question_type,
                    # caregiver=care_giver
                )
            msg = 'wellbeing adolesent saved successful'
            messages.add_message(request, messages.INFO, msg)
            url = reverse('ovc_view', kwargs={'id': id})
            return HttpResponseRedirect(url)
            # url = reverse('ovc_view', kwargs={'id': id})
            # # return HttpResponseRedirect(reverse(forms_registry))
            # return HttpResponseRedirect(url)
    except Exception as e:
        msg = 'wellbeing adolescent save error : (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        print('Error saving wellbeing adolescent : %s' % str(e))
        return HttpResponseRedirect(reverse(forms_home))

    # get household members/ caretaker/ household_id
    household_id = None
    try:
        ovcreg = get_object_or_404(OVCRegistration, person_id=id, is_void=False)
        caretaker_id = ovcreg.caretaker_id if ovcreg else None
        ovchh = get_object_or_404(OVCHouseHold, head_person=caretaker_id, is_void=False)
        household_id = ovchh.id if ovchh else None
    except Exception as e:
        print(str(e))
        msg = 'Error getting household identifier: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        return HttpResponseRedirect(reverse(forms_registry))
    # get child data
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id', 'relationship_type_id']
    vals = get_dict(field_name=check_fields)
    ovc_id = int(id)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)

    form = WellbeingAdolescentForm(initial={'household_id': household_id})
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

    return render(request,
                  'forms/new_wellbeingadolescent.html',
                  {
                      'form': form,
                      'init_data': init_data,
                      'vals': vals,
                      'person': id,
                      'care_giver': care_giver

                  })


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def hiv_status(request):
    try:
        if request.method == 'POST':
            child = request.POST.get('child')
            child_id = RegPerson.objects.get(id=child)
            house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child_id).house_hold_id)
            event_type_id = 'HIVS'
            event_counter = OVCCareEvents.objects.filter(
                event_type_id=event_type_id, person=child, is_void=False).count()

            ovccareevent = OVCCareEvents.objects.create(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                created_by=request.user.id,
                person=RegPerson.objects.get(pk=int(child)),
                house_hold=house_hold,
                date_of_event=timezone.now()
            )
            hiv_status = request.POST.get('hiv_statuss')
            OVCHivStatus(
                person=RegPerson.objects.get(pk=int(child)),
                hiv_status=request.POST.get('hiv_statuss'),
                event=ovccareevent,
                date_of_event=request.POST.get('date_of_testing')
            ).save()

            msg = 'HIV status updated successful'
            messages.add_message(request, messages.INFO, msg)

            response = redirect('ovc_edit')
            return response

    except Exception as e:
        msg = 'hiv status save error : (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        print('Error saving hiv status : %s' % str(e))
        return HttpResponseRedirect(reverse(forms_home))


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_hivscreeningtool(request, id):
    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id']
    vals = get_dict(field_name=check_fields)
    hiv_screen = None
    hiv_facility = None
    if request.method == 'POST':
        try:

            form = HIV_SCREENING_FORM(request.POST, initial={'person': id})
            if True:
                child = RegPerson.objects.get(id=id)
                house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
                event_type_id = 'HRST'

                """ Save hiv_screening-event """
                # get event counter
                event_counter = OVCCareEvents.objects.filter(
                    event_type_id=event_type_id, person=id, is_void=False).count()
                # save event
                ovccareevent = OVCCareEvents.objects.create(
                    event_type_id=event_type_id,
                    event_counter=event_counter,
                    event_score=0,
                    created_by=request.user.id,
                    person=RegPerson.objects.get(pk=int(id)),
                    house_hold=house_hold
                )

                try:
                    parent_consentdate = form.data['HIV_RS_15']
                except:
                    parent_consentdate = "1900-01-01"

                try:
                    referal_madedate = form.data['HIV_RS_17']
                except:
                    referal_madedate = "1900-01-01"

                try:
                    referal_completeddate = form.data['HIV_RS_19']
                except:
                    referal_completeddate = "1900-01-01"

                try:
                    art_referaldate = form.data['HIV_RS_22']
                except:
                    art_referaldate = "1900-01-01"

                try:
                    art_refer_completeddate = form.data['HIV_RS_24']
                except:
                    art_refer_completeddate = "1900-01-01"

                if parent_consentdate:
                    parent_consentdate = parent_consentdate

                else:
                    parent_consentdate = timezone.now()

                if referal_madedate:
                    referal_madedate = referal_madedate

                else:
                    referal_madedate = timezone.now()

                if referal_completeddate:
                    referal_completeddate = referal_completeddate

                else:
                    referal_completeddate = timezone.now()

                if art_referaldate:
                    art_referaldate = art_referaldate

                else:
                    art_referaldate = timezone.now()

                if art_refer_completeddate:
                    art_refer_completeddate = art_refer_completeddate

                else:
                    art_refer_completeddate = timezone.now()
                # converting values AYES and ANNO to boolean true/false
                boolean_fields = [
                    'HIV_RS_01',
                    'HIV_RS_02',
                    'HIV_RS_03',
                    'HIV_RS_03A',
                    'HIV_RS_04',
                    'HIV_RS_05',
                    'HIV_RS_06',
                    'HIV_RS_07',
                    'HIV_RS_08',
                    'HIV_RS_09',
                    'HIV_RS_10',
                    'HIV_RS_11',
                    'HIV_RS_14',
                    'HIV_RS_16',
                    'HIV_RS_18',
                    'HIV_RS_18A',
                    'HIV_RS_21',
                    'HIV_RS_23',

                ]

                data_to_save = {}

                for key, value in request.POST.items():
                    if key in boolean_fields:
                        data_to_save.update({
                            key: True if value == "AYES" else False
                        })
                    else:
                        data_to_save.update({key: value})

                facility = data_to_save.get('HIV_RA_3Q6')
                if facility:
                    facility_res = OVCFacility.objects.get(id=facility).facility_code
                else:
                    facility_res = None
                
                skipped = boolean_fields - data_to_save.keys()
                for skip in skipped:
                    data_to_save[skip] = False

                print(data_to_save)
                # breakpoint()
                ovcscreeningtool = OVCHIVRiskScreening.objects.create(
                    person=RegPerson.objects.get(pk=int(id)),
                    date_of_event=data_to_save.get('HIV_RA_1A'),
                    test_done_when=data_to_save.get('HIV_RS_03'),  # date of assesment
                    test_donewhen_result=data_to_save.get('HIV_RS_03A'),
                    caregiver_know_status=data_to_save.get('HIV_RS_01'),
                    caregiver_knowledge_yes=data_to_save.get('HIV_RS_02'),
                    parent_PLWH=data_to_save.get('HIV_RS_04'),
                    child_sick_malnourished=data_to_save.get('HIV_RS_05'),
                    child_sexual_abuse=data_to_save.get('HIV_RS_06'),
                    adol_sick=data_to_save.get('HIV_RS_07'),
                    adol_sexual_abuse=data_to_save.get('HIV_RS_08'),
                    sex=data_to_save.get('HIV_RS_09'),
                    sti=data_to_save.get('HIV_RS_10'),
                    hiv_test_required=data_to_save.get('HIV_RS_11'),
                    parent_consent_testing=data_to_save.get('HIV_RS_14'),
                    parent_consent_date=parent_consentdate,
                    referral_made=data_to_save.get('HIV_RS_16'),
                    referral_made_date=referal_madedate,
                    referral_completed=data_to_save.get('HIV_RS_18'),
                    referral_completed_date=referal_completeddate,
                    not_completed=data_to_save.get('HIV_RS_18A'),
                    test_result=data_to_save.get('HIV_RS_18B'),
                    art_referral=data_to_save.get('HIV_RS_21'),
                    art_referral_date=art_referaldate,
                    art_referral_completed=data_to_save.get('HIV_RS_23'),
                    art_referral_completed_date=art_refer_completeddate,
                    facility_code=facility_res,
                    event=ovccareevent
                )
                msg = 'HIV risk screening saved successful'
                messages.add_message(request, messages.INFO, msg)
                url = reverse('ovc_view', kwargs={'id': id})
                return HttpResponseRedirect(url)
        except Exception as e:
            from django.db import connection
            msg = "failed to save data", e
            messages.add_message(request, messages.ERROR, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)

    else:
        form = HIV_SCREENING_FORM()
        event = OVCCareEvents.objects.filter(person_id=id).values_list('event')
        hiv_screen = OVCHIVRiskScreening.objects.filter(event_id__in=event).order_by('date_of_event')
        facility_hivrisk = OVCHIVRiskScreening.objects.filter(event_id__in=event).values_list('facility_code').order_by(
            'date_of_event')
        facilitiy_ids = [i[0] for i in facility_hivrisk]
        hiv_facility = OVCFacility.objects.filter(id__in=facilitiy_ids)

    return render(request, 'forms/new_hivscreeningtool.html',
                  {'form': form, 'init_data': init_data, 'vals': vals, 'hiv_screen': hiv_screen,
                   'hiv_facility': hiv_facility})


# New HIV Manangement Form
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_hivmanagementform(request, id):
    if request.method == 'POST':
        # try:
        data = request.POST
        print(data)
        msg = ''
        person = RegPerson.objects.get(id=id)
        event_date = request.POST.get('HIV_MGMT_2_A')
        event_type_id = 'MGMT'
        child = RegPerson.objects.get(id=id)
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)

        event_counter = OVCCareEvents.objects.filter(
            event_type_id=event_type_id, person=id, is_void=False).count()+1
        # save event
        
        ovccareevent = OVCCareEvents.objects.create(
            event_type_id=event_type_id,
            event_counter=event_counter,
            event_score=0,
            created_by=request.user.id,
            person=person,
            house_hold=house_hold
        )

        

        _HIV_MGMT_1_E = False
        _HIV_MGMT_1_F = False
        _HIV_MGMT_1_G = False
        if (request.POST.get('HIV_MGMT_1_E')):
            _HIV_MGMT_1_E = request.POST.get('HIV_MGMT_1_E')
        if (request.POST.get('HIV_MGMT_1_F')):
            _HIV_MGMT_1_F = request.POST.get('HIV_MGMT_1_F')
        if (request.POST.get('HIV_MGMT_1_G')):
            _HIV_MGMT_1_G = request.POST.get('HIV_MGMT_1_G')

        _HIV_MGMT_2_O_1 = False
        if (request.POST.get('HIV_MGMT_2_O_1')):
            _HIV_MGMT_2_O_1 = request.POST.get('HIV_MGMT_2_O_1')

        _HIV_MGMT_1_E_DATE = "1900-01-01"
        _HIV_MGMT_1_F_DATE = "1900-01-01"
        _HIV_MGMT_1_G_DATE = "1900-01-01"

        if (request.POST.get('HIV_MGMT_1_E_DATE')):
            _HIV_MGMT_1_E_DATE = request.POST.get('HIV_MGMT_1_E_DATE')
        if (request.POST.get('HIV_MGMT_1_F_DATE')):
            _HIV_MGMT_1_F_DATE = request.POST.get('HIV_MGMT_1_F_DATE')
        if (request.POST.get('HIV_MGMT_1_G_DATE')):
            _HIV_MGMT_1_G_DATE = request.POST.get('HIV_MGMT_1_G_DATE')

        new_pk = ovccareevent.pk
        try:
            qry = OVCHIVManagement(
                person=person,
                hiv_confirmed_date=request.POST.get('HIV_MGMT_1_A'),
                baseline_hei=request.POST.get('HIV_MGMT_1_C'),
                treatment_initiated_date=request.POST.get('HIV_MGMT_1_B'),
                firstline_start_date=request.POST.get('HIV_MGMT_1_D'),  # date
                substitution_firstline_arv=_HIV_MGMT_1_E,
                substitution_firstline_date=_HIV_MGMT_1_E_DATE,
                switch_secondline_arv=_HIV_MGMT_1_F,
                switch_secondline_date=_HIV_MGMT_1_F_DATE,
                switch_thirdline_arv=_HIV_MGMT_1_G,
                switch_thirdline_date=_HIV_MGMT_1_G_DATE,
                visit_date=request.POST.get('HIV_MGMT_2_A'),
                duration_art=request.POST.get('HIV_MGMT_2_B'),
                height=request.POST.get('HIV_MGMT_2_C'),
                muac=request.POST.get('HIV_MGMT_2_D'),
                adherence=request.POST.get('HIV_MGMT_2_E'),
                adherence_drugs_duration=request.POST.get('HIV_MGMT_2_F'),
                adherence_counselling=request.POST.get('HIV_MGMT_2_G'),
                treatment_suppoter=request.POST.get('HIV_MGMT_2_H_2'),
                treatment_supporter_relationship=request.POST.get('HIV_MGMT_2_H_1'),
                treatment_supporter_gender=request.POST.get('HIV_MGMT_2_H_3'),
                treament_supporter_hiv=request.POST.get('HIV_MGMT_2_H_5'),
                viral_load_results=request.POST.get('HIV_MGMT_2_I_1'),
                viral_load_date=request.POST.get('HIV_MGMT_2_I_DATE'),
                treatment_supporter_age=request.POST.get('HIV_MGMT_2_H_4'),
                detectable_viralload_interventions=request.POST.get('HIV_MGMT_2_J'),
                disclosure=request.POST.get('HIV_MGMT_2_K'),
                muac_score=request.POST.get('HIV_MGMT_2_L_1'),
                bmi=request.POST.get('HIV_MGMT_2_L_2'),
                nutritional_support=request.POST.get('HIV_MGMT_2_M'),
                support_group_status=request.POST.get('HIV_MGMT_2_N'),
                nhif_enrollment=_HIV_MGMT_2_O_1,
                nhif_status=request.POST.get('_HIV_MGMT_2_O_2'),
                referral_services=request.POST.get('HIV_MGMT_2_P'),
                nextappointment_date=request.POST.get('HIV_MGMT_2_Q'),
                peer_educator_name=request.POST.get('HIV_MGMT_2_R'),
                peer_educator_contact=request.POST.get('HIV_MGMT_2_S'),
                event=ovccareevent,
                date_of_event=request.POST.get('HIV_MGMT_2_A'),
                timestamp_created=timezone.now()
            ).save()

            msg = 'HIV management saved successfully'
            messages.add_message(request, messages.INFO, msg)

        except Exception as e:
            msg = f'HIV Management form didnt save successfully: {e}'
            messages.add_message(request, messages.ERROR, msg)

    
        
        # except Exception, e:
        #     from django.db import connection
        #     msg="failed to save data",e
        #     messages.add_message(request, messages.ERROR, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)
    else:
        try:
            init_data = RegPerson.objects.filter(pk=id)
            check_fields = ['sex_id']
            vals = get_dict(field_name=check_fields)
            form_arvtherapy = HIV_MANAGEMENT_ARV_THERAPY_FORM(initial={'person': id})
            child_hiv_status = OVCRegistration.objects.get(person=id).hiv_status
            form = HIV_MANAGEMENT_VISITATION_FORM(initial={'person': id})

            return render(request,
                          'forms/new_hivmanagementform.html',
                          {'form': form,
                           'form_arvtherapy': form_arvtherapy,
                           'init_data': init_data,
                           'child_hiv_status': child_hiv_status,
                           'vals': vals})
        except Exception as e:
            print(e)


# DREAMS Service Uptake Form
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def new_dreamsform(request, id):
    try:
        init_data = RegPerson.objects.filter(pk=id)
        check_fields = ['sex_id']
        vals = get_dict(field_name=check_fields)
        print(vals)
        form = DREAMS_FORM(initial={'person': id})
    except:
        pass
    
    return render(request,
                  'forms/new_dreamsform.html',
                  {'form': form, 'init_data': init_data,
                   'vals': vals})



def new_benchmarkmonitoring(request, id):
    """
        Function that processes the new benchmark monitoring
        form
        Args:
            params(int): id
                        :request
        Returns:
            new_benchmarkmonitoring.html
    """
    child = RegPerson.objects.get(id=id)
    if request.method == 'POST':

        # get submitted data
        benchmark1 = request.POST.get("BENCHMARKMONITORING_001")
        benchmark2 = request.POST.get("BENCHMARKMONITORING_002")
        benchmark3 = request.POST.get("BENCHMARKMONITORING_003")
        benchmark4 = request.POST.get("BENCHMARKMONITORING_004")
        benchmark5 = request.POST.get("BENCHMARKMONITORING_005")
        benchmark6 = request.POST.get("BENCHMARKMONITORING_006")
        benchmark7 = request.POST.get("BENCHMARKMONITORING_007")
        benchmark8 = request.POST.get("BENCHMARKMONITORING_008")
        benchmark9 = request.POST.get("BENCHMARKMONITORING_009")
        date_of_event = request.POST.get("monitoring_date")
        event_name = 'MONITORING'

        # save events

        try:
            event_id = save_event(request, id, event_name, date_of_event, )

        except exception as e:
            print("an error occured ", e)

        benchmark = OVCBenchmarkMonitoring(
            person_id=id,
            benchmark_1=benchmark1,
            benchmark_2=benchmark2,
            benchmark_3=benchmark3,
            benchmark_4=benchmark4,
            benchmark_5=benchmark5,
            benchmark_6=benchmark6,
            benchmark_7=benchmark7,
            benchmark_8=benchmark8,
            benchmark_9=benchmark9,
            event=event_id
        )
        benchmark.save()



    else:
        # caregiver name
        # caregiver ID

        form = BenchmarkMonitoringForm()

        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

        context = {
            'form': form,
            'care_giver': care_giver

        }

        return render(request, 'forms/new_benchmarkmonitoring.html', context)


def new_case_closure(request, id):
    try:

        if request.method == 'POST':
            data = request.POST
            print(data)
            closure_reason = request.POST.get("CASE_CL001")
            if closure_reason=='1':
                reason=request.POST.get("CASE_CL001")
            elif closure_reason=='2':
                reason = request.POST.get("CASE_CL023")
            else:
                reason =" "

            attrition_reason1 = request.POST.get("CASE_CL027")

            transfer_completed = request.POST.get("CASE_CL010")
            followup_time = request.POST.get("CASE_CL011")
            informed = request.POST.get("CASE_CL012")
            copy_sent = request.POST.get("CASE_CL013")
            file_stored1 = request.POST.get("CASE_CL014")
            attrition_reason2 = request.POST.get("CASE_CL030")
            manager_report = request.POST.get("CASE_CL029")
            head_hh_linked= request.POST.get("CASE_CL028")
            exit_reason = request.POST.get("CASE_CL031")
            date = request.POST.get("CASE_CL026")
            files_completed = request.POST.get("CASE_CL006")
            phone_number = request.POST.get("CASE_CL007")
            informed_graduation = request.POST.get("CASE_CL008")
            receiving_org = request.POST.get("CASE_CL002")


            if receiving_org:
                org_res = RegOrgUnit.objects.get(id=receiving_org).id

            else:
                org_res = ''


            person = RegPerson.objects.get(pk=int(id))
            care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=person).caretaker_id)

            organization = RegOrgUnit.objects.get(id=OVCRegistration.objects.get(person=person).child_cbo_id)
            event_type_id = 'WBGA'
            date_of_closure = timezone.now()

            """ Save evaluation-event """
    except Exception as e:
        raise e


def new_hei_tracker(request, id):
    hei8 = hei9 = hei10 = hei11 = hei12 = hei13 = hei14 = hei15 = hei16 = hei17 = hei18 = hei19 = hei20 = hei21 = hei22 = hei23 = hei24 = hei25 = hei26 = hei27 = hei28 = hei29 = hei30 = hei31 = hei32 = hei33 = hei34 = hei35 = hei36 = ''
    contact_date1 = contact_date2 = contact_date3 = contact_date4 = contact_date5 = '1900-01-01'
    try:
        # import pdb

        if request.method == 'POST':
            comments = ['WB_AD_GEN_4_2']
            ignore_request_values = ['household_id', 'csrfmiddlewaretoken']

            # household_id = request.POST.get('household_id')
            # hse_uuid = uuid.UUID(household_id)
            # house_holds = OVCHouseHold.objects.get(pk=hse_uuid)
            person = RegPerson.objects.get(pk=int(id))
            event_type_id = 'WBGA'
            date_of_wellbeing_event = timezone.now()

            """ Save Wellbeing-event """
            # get event counter
            event_counter = OVCCareEvents.objects.filter(
                event_type_id=event_type_id, person=id, is_void=False).count()
            # save event
            ovccareevent = OVCCareEvents(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                date_of_event=date_of_closure,
                created_by=request.user.id,
                person=RegPerson.objects.get(pk=int(id)),


            )
            ovccareevent.save()
            # Saving OVC Case Closure
            OVCCareCaseExit.objects.filter(case_clouse_id=id).create(
                person=person,
                caregiver=care_giver,
                rec_organization =org_res,
                organization=organization,
                reason=reason,
                attrition_reason=attrition_reason1,
                transfer_form_completed=transfer_completed,
                follow_up_frequency=followup_time,
                sp_informed_tarnsfer=informed,
                family_folder_sent=copy_sent,
                files_stored=file_stored1,
                attrition_documented=attrition_reason2,
                manager_report=manager_report,
                head_hh_linked=head_hh_linked,
                exit_reason_stored=exit_reason,
                date_of_closure=date,
                case_files_completed=files_completed,
                cw_phone_household=phone_number,
                sp_informed_graduation=informed_graduation,
                event=ovccareevent)



            msg = 'form case closure saved successful'
            pmtctevent = PMTCTEvents(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                date_of_event=date_of_wellbeing_event,
                created_by=request.user.id,
                person=RegPerson.objects.get(pk=int(id)),
            )
            pmtctevent.save()
            # get questions for adolescent
            questions = PMTCTQuestions.objects.filter(code__startswith='HEI')
            ovc_id = int(id)
            child = RegPerson.objects.get(is_void=False, id=ovc_id)
            care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
            for question in questions:
                answer = request.POST.get(question.question)
                if answer is None:
                    answer = ''
                PMTCTHEI(
                    person=RegPerson.objects.get(pk=int(id)),
                    question_code=question.code,
                    question=question,
                    answer=answer,
                    event=pmtctevent,
                    # date_of_event=timezone.now(),
                    question_id=question.question_id,
                    caregiver=care_giver
                ).save()

            msg = 'hei  saved successful'
            messages.add_message(request, messages.INFO, msg)
            url = reverse('ovc_view', kwargs={'id': id})
            return HttpResponseRedirect(url)
            # url = reverse('ovc_view', kwargs={'id': id})
            # # return HttpResponseRedirect(reverse(forms_registry))
            # return HttpResponseRedirect(url)
    except Exception as e:
        msg = 'form Case closure save error : (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        print('Error saving form evaluation : %s' % str(e))
        return HttpResponseRedirect(reverse(forms_home))

    init_data = RegPerson.objects.filter(pk=id)
    check_fields = ['sex_id', 'relationship_type_id','yesno_id','exit_reason_id','REASON_SS']
    vals = get_dict(field_name=check_fields)
    ovc_id = int(id)
    print(f'This is ovc {ovc_id} Thisid {id}')
    child = RegPerson.objects.get(is_void=False, id=ovc_id)

    form = CaseClosureForm()
    event = OVCCareEvents.objects.filter(person_id=id).values_list('event')

    case_closure_date= OVCCareCaseExit.objects.filter(event_id__in=event,is_void=False).order_by('date_of_closure')



    org_names = []

    i = 0
    for org_name in range(len(case_closure_date)):
        if case_closure_date[i].rec_organization != '':
            print (RegOrgUnit.objects.get(id=case_closure_date[i].rec_organization))
            i += 1


    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)


    return render(request,
                  'forms/new_case_closure.html',
                  {'form': form,
                   'init_data': init_data,
                   'care_giver': care_giver,
                   'case_closure': case_closure_date,

                   'id': id,
                   'vals': vals})




def delete_case_closure(request, id):

    delete_caseclosure = OVCCareCaseExit.objects.filter(case_clouse_id=id)
    person_id = OVCCareCaseExit.objects.get(case_clouse_id=id).person_id
    delete_caseclosure.update(is_void=True)
    url = reverse('new_case_closure', kwargs={'id': person_id})
    msg = "Data deleted successfully"
    messages.add_message(request,messages.INFO, msg)

    return HttpResponseRedirect(url)

def edit_case_closure(request, id):
    """Some default page for Server Errors."""



    try:

        posted_data = OVCCareCaseExit.objects.get(case_clouse_id=id, is_void=False)
        person_id = OVCCareCaseExit.objects.get(case_clouse_id=id).person_id
        if request.method == 'POST':
            #closure_reason = request.POST.get("CASE_CL001")
            attrition_reason1 = request.POST.get("CASE_CL027")

            transfer_completed = request.POST.get("CASE_CL010")
            followup_time = request.POST.get("CASE_CL011")
            informed = request.POST.get("CASE_CL012")
            copy_sent = request.POST.get("CASE_CL013")
            file_stored1 = request.POST.get("CASE_CL014")
            attrition_reason2 = request.POST.get("CASE_CL030")
            manager_report = request.POST.get("CASE_CL029")
            head_hh_linked = request.POST.get("CASE_CL028")
            exit_reason = request.POST.get("CASE_CL031")
            date = request.POST.get("CASE_CL026")
            files_completed = request.POST.get("CASE_CL006")
            phone_number = request.POST.get("CASE_CL007")
            informed_graduation = request.POST.get("CASE_CL008")
            receiving_org = request.POST.get("CASE_CL002")
            if receiving_org:
                org_res = RegOrgUnit.objects.get(id=receiving_org).id
            else:
                org_res = ''

            OVCCareCaseExit.objects.filter(case_clouse_id=id).update(
                rec_organization=org_res,
                # reason=closure_reason,
                attrition_reason=attrition_reason1,
                transfer_form_completed=transfer_completed,
                follow_up_frequency=followup_time,
                sp_informed_tarnsfer=informed,
                family_folder_sent=copy_sent,
                files_stored=file_stored1,
                attrition_documented=attrition_reason2,
                manager_report=manager_report,
                head_hh_linked=head_hh_linked,
                exit_reason_stored=exit_reason,
                date_of_closure=date,
                case_files_completed=files_completed,
                cw_phone_household=phone_number,
                sp_informed_graduation=informed_graduation,
                )



            msg = 'form case closure edited successful'
            messages.add_message(request, messages.INFO, msg)
            url = reverse('new_case_closure', kwargs={'id': person_id})
            return HttpResponseRedirect(url)

        gotten_data = {
            'CASE_CL001': posted_data.reason,
            'CASE_CL023': posted_data.reason,
            'CASE_CL002': posted_data.rec_organization,
            'CASE_CL027': posted_data.attrition_reason,

            'CASE_CL010': posted_data.transfer_form_completed,
            'CASE_CL011': posted_data.follow_up_frequency,
            'CASE_CL012': posted_data.sp_informed_tarnsfer,
            'CASE_CL013': posted_data.family_folder_sent,
            'CASE_CL014': posted_data.files_stored,
            'CASE_CL030': posted_data.attrition_documented,
            'CASE_CL029': posted_data.manager_report,
            'CASE_CL028': posted_data.head_hh_linked,
            'CASE_CL031': posted_data.exit_reason_stored,
            'CASE_CL026': posted_data.date_of_closure,
            'CASE_CL006': posted_data.case_files_completed,
            'CASE_CL007': posted_data.cw_phone_household,
            'CASE_CL008': posted_data.sp_informed_graduation,

        }

        form = CaseClosureForm(data=gotten_data)
        return render(request, 'forms/edit_case_closure.html',
                        {'form': form, 'status': 200})



    except Exception as e:
        print("error with OVC case closure Editing - %s" % (str(e)))
        # raise e
        msg = "Error occured during OVC case closure edit"
        messages.add_message(request, messages.ERROR, msg)
        url = reverse('new_case_closure', kwargs={'id': person_id})
        return HttpResponseRedirect(url)

        msg = 'HEI tracker save error: (%s)' % (str(e))
        messages.add_message(request, messages.ERROR, msg)
        print('Error saving HEI tracker : %s' % str(e))
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(reverse(url))


# New Cpara action functionality
def new_cpara(request, id):
    if request.method == 'POST':
        data = request.POST
        child = RegPerson.objects.get(id=int(id))
        form = CparaAssessment()
        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
        ovc_id = int(id)
        creg = OVCRegistration.objects.get(is_void=False, person_id=ovc_id)

        # Get house hold
        hhold = OVCHHMembers.objects.get(is_void=False, person_id=id)
        # Get HH members
        hhid = hhold.house_hold_id
        hhmqs = OVCHHMembers.objects.filter(is_void=False, house_hold_id=hhid).order_by("-hh_head")
        hhmembers2 = hhmqs.exclude(person_id=id)
        hhmembers = hhmembers2.exclude(person=care_giver)
        date_previous = data.get('CP2d')

        questions = OVCCareQuestions.objects.filter(
            code__startswith='CP', is_void=False).values()

        date_of_event = data.get('d_o_a')
        event_date = data.get('d_o_a')

        event = OVCCareEvents.objects.create(
                event_type_id='cpr',
                created_by=request.user.id,
                person=child,
                house_hold=house_hold,
                date_of_event=event_date
            )

        for question in questions: 
            d_previous=data.get('CP2d')
            date_previous = d_previous if d_previous else None
            answer = data.get(question['code'])
            # print(f'date_previous{date_previous} date of event {date_of_event}')
            
            if answer is None:
                answer = 'No'
            elif answer == 'AYES':
                answer=True
            elif answer=='ANNO':
                answer=False
            elif answer=='ANA':
                answer='Na'
            else:
                answer='No'    
            
            try:
                OVCCareCpara.objects.create(
                    person=child,
                    caregiver=care_giver,
                    question=OVCCareQuestions.objects.get(question_id=question['question_id']),
                    question_code=question['code'],
                    answer=answer,
                    household=house_hold,
                    question_type=question['question_type'],
                    domain=question['domain'],
                    event=event,
                    date_of_event=event_date,
                    date_of_previous_event=date_previous, 
                )
                    
            except Exception as e:
                print(f'The OVC Cpara Form didnt save: {e}')
                msg1 = f'The OVC Cpara Form didnt save:  {e}'
                messages.add_message(request, messages.ERROR,msg1)
               

        # converts the filtered objects to a list
        ovc_score = data.get('bench_array').replace('[', '').replace(']', '').split(',')

        
        try:
            OVCCareBenchmarkScore.objects.create(
                household=house_hold,
                benchmark_1=int(ovc_score[0]),
                benchmark_2=int(ovc_score[1]),
                benchmark_3=int(ovc_score[2]),
                benchmark_4=int(ovc_score[3]),
                benchmark_5=int(ovc_score[4]),
                benchmark_6=int(ovc_score[5]),
                benchmark_7=int(ovc_score[6]),
                benchmark_8=int(ovc_score[7]),
                benchmark_9=int(ovc_score[8]),
                score=sum([int(i) for i in ovc_score]),
                event=event,
                care_giver=care_giver    
            
            )
        except Exception as e:
            print (f"Error while saving to ovccarebenchmark: {e}" )
            messages.add_message(request, messages.INFO,"f'Error while saving to ovccarebenchmark: {e}'")


        # sub_pop = {'CP6d_1':'double','CP6d_2':'AGYW','CP6d_3':'HEI','CP6d_4':'FSW','CP6d_5':'PLHIV','CP6d_6':'CLHIV','CP6d_7':'SVAC'}

        # try:
        #     for q, v in sub_pop.items():
        #         if data.get(q) == 'on':
        #             OVCSubPopulation.objects.create(
        #                 person=child,
        #                 criteria=v,
        #                 date_of_event=convert_date(date_of_event),
        #                 timestamp_created = timezone.now(),
        #                 event=event
        #             )
        # except Exception as e:
        #     print(f'The error is {e}')

        hhold = OVCHHMembers.objects.get(is_void=False, person_id=id)
        # Get HH members
        hhid = hhold.house_hold_id
        hhmqs = OVCHHMembers.objects.filter(is_void=False, house_hold_id=hhid).order_by("-hh_head")
        hhmembers2 = hhmqs.exclude(person_id=id)
        hhmembers = hhmembers2.exclude(person=care_giver)

        # start of appending the results



        # Save data for table data for 3.1 , 3.2 and 3.3
        quiz_saved = OVCCareQuestions.objects.filter(code__startswith='CP', is_void=False)

        # get a list of the question code from the OVC Care question table
        saved_quiz = [i.code for i in quiz_saved]

        # get a list of the question code from the POST methods
        post_quiz = [i for i in data.keys()]

        to_process = set(post_quiz)-set(saved_quiz)
        
        # Gets the values for questions 3.1 to 3.6 individual cpara
        # ['43_CP16q', '60_CP16q', '23_CP15q', '23_CP16q', '43_CP15q', '60_CP17q', '60_CP15q', '43_CP17q', '23_CP17q']
        q31 = 'CP15q'
        q32 = 'CP16q'
        q33 = 'CP17q'
        ind_cpara = ['CP15q','CP16q','CP17q']
        bench_three=[]
        for i, element in enumerate(to_process):
            if q31 in element:
                bench_three.append(element)
            elif q32 in element:
                bench_three.append(element)
            elif q33 in element:
                bench_three.append(element)
        
        for b_item in bench_three:            
            person_id_bench=b_item.split('_')[0]
            quiz_code=b_item.split('_')[1]
            
            print(f'The person id {person_id_bench} and the quiz code is {quiz_code}')
        
            child4 = RegPerson.objects.get(id=int(person_id_bench))
            
            question1= OVCCareQuestions.objects.filter(code=quiz_code).values()

            question_inst= OVCCareQuestions.objects.get(code=quiz_code)

            ind_answer = data.get(b_item)

            if ind_answer == 'AYES':
                ind_answer = True
            else:
                ind_answer = False
            # breakpoint()
            
            try:
                OVCCareIndividaulCpara.objects.create(
                    person=child4,
                    caregiver=care_giver,
                    question_code=quiz_code,
                    question=question_inst,
                    answer=ind_answer,
                    household=house_hold,
                    question_type=question1[0]['question_type'],
                    domain=question1[0]['domain'],
                    date_of_event=event_date,
                    date_of_previous_event=date_previous,
                    event=event

                 )
            except Exception as e:
                error_message=f'The OVCCareIndividaulCpara failed: {e}'
                print(error_message)

        else:
            hh_members = []
            for h_mmembers in hhmembers:
                hh_person_ids = h_mmembers.person.id
                hh_members.append(hh_person_ids)
            hh_members.append(id)
            # breakpoint()
            for hh_person_id in hh_members:
                for ind_cpa in ind_cpara:   
                    try:
                        OVCCareIndividaulCpara.objects.create(
                        person=RegPerson.objects.get(id=hh_person_id),
                        caregiver=care_giver,
                        question_code=ind_cpa,
                        question=OVCCareQuestions.objects.get(code=ind_cpa),
                        answer=True,
                        household=house_hold,
                        question_type='OVC',
                        domain='DHNU',
                        date_of_event=event_date,
                        date_of_previous_event=date_previous,
                        event=event

                        )
                    except Exception as e:
                        error_message=f'The OVCCareIndividaulCpara (No) failed: {e}'
                        print(error_message)                

            # breakpoint()
            

        # Gets the values for questions in OVC sub population
        # ['23_CP6d_2', 'CP6d_7', '23_CP6d_6', 'CP6d_1', '23_CP6d_5', '43_CP6d_4', '43_CP6d_6', '43_CP6d_2', '23_CP6d_1', 'CP6d_5', '43_CP6d_7', '43_CP6d_5', '23_CP6d_3', '23_CP6d_4', '23_CP6d_7']
        ovc_pp = 'CP6d'
        sub_pop = {'CP6d_1':'double','CP6d_2':'AGYW','CP6d_3':'HEI','CP6d_4':'FSW','CP6d_5':'PLHIV','CP6d_6':'CLHIV','CP6d_7':'SVAC','CP6d_8':'AHIV'}
        ovc_sub_pp=[]
        for i, element in enumerate(to_process):
            if ovc_pp in element:
                ovc_sub_pp.append(element)

        for ovc_sub in ovc_sub_pp:
            if len(ovc_sub)<=6:
                ovc_sub_id=id
                ovc_sub_q = ovc_sub
                
            else:
                ovc_sub_id=ovc_sub.split('_')[0]
                ovc_sub_q=ovc_sub.split('_')[1]+'_'+ovc_sub.split('_')[2]
                

            child2 = RegPerson.objects.get(id=int(ovc_sub_id))

            try:
                OVCSubPopulation.objects.create(
                    person=child2,
                    criteria=sub_pop[ovc_sub_q],
                    event=event,
                    date_of_event=event_date,
                )
            except Exception as e:
                error_message = f'The OVC sub pop save append failed {e}'
                print(error_message)


        # Gets the values for questions in Question 6.3 
        # ['60_CP27q2', '23_CP27q2', '43_CP27q2']
        q61 = 'CP27q2'
     
        quiz_63=[]
        for i, element in enumerate(to_process):
            if q61 in element:
                quiz_63.append(element) 

        for quizs in quiz_63:
            quizs_id=quizs.split('_')[0]
            quizs_code='CP27q'

            # child3 = RegPerson.objects.filter(id=quizs_id)
            quest_type=OVCCareQuestions.objects.filter(code=quizs_code).values()

            quest_type_1=OVCCareQuestions.objects.get(code=quizs_code)

            print(f'The person id: {quizs_id } and the Quiz code is : {quizs_code}')

            child3 = RegPerson.objects.get(id=int(quizs_id))
            # pdb.set_trace()

        
            try:
                OVCCareCpara.objects.create(
                    person=child3,
                    caregiver=care_giver,
                    question=quest_type_1,
                    question_code=quizs_code,
                    answer=data.get(quizs),
                    household=house_hold,
                    question_type=quest_type[0]['question_type'],
                    domain=quest_type[0]['domain'],
                    event=event,
                    date_of_event=date_of_event,
                    date_of_previous_event=date_previous, 
                )
                    
            except Exception as e:
                print(f'The OVC Cpara Form append didnt save:  {e}')
            

        
        url = reverse('ovc_view', kwargs={'id': id})
        msg = f'Cpara data saved succesfully'
        messages.add_message(request, messages.INFO,msg)  
        return HttpResponseRedirect(url)

        
    child = RegPerson.objects.get(id=id)
    ovc_id = int(id)
    creg = OVCRegistration.objects.get(is_void=False, person_id=ovc_id)
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

    house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)

    # Get house hold
    hhold = OVCHHMembers.objects.get(is_void=False, person_id=id)
    # Get HH members
    hhid = hhold.house_hold_id
    hhmqs = OVCHHMembers.objects.filter(is_void=False, house_hold_id=hhid).order_by("-hh_head")
    hhmembers2 = hhmqs.exclude(person_id=id)
    hhmembers = hhmembers2.exclude(person=care_giver)

    # Get child geo
    child_geos = RegPersonsGeo.objects.select_related().filter(
        person=child, is_void=False, date_delinked=None)
    all_geos_county, all_geos_wards, all_geos = [], [], []
    for person_geo in child_geos:
        geo_name = str(person_geo.area.area_id)
        geo_type = person_geo.area.area_type_id
        if geo_type == 'GPRV':
            all_geos_county.append(geo_name)
        elif geo_type == 'GDIS':
            all_geos.append(geo_name)
        else:
            all_geos_wards.append(geo_name)
    if all_geos:
        geos = ', '.join(all_geos)
    else:
        geos = None
    if all_geos_wards:
        geo_wards = ', '.join(all_geos_wards)
    else:
        geo_wards = None
    if all_geos_county:
        geo_county = ', '.join(all_geos_county)
    # geo_wards = geo_wards

    if geo_wards is None:
        ward = None
        subcounty = None
        county = None
    else:
        ward_id = int(geo_wards)
        ward = SetupGeography.objects.get(area_id=ward_id)
        subcounty = SetupGeography.objects.get(area_id=ward.parent_area_id)
        county = SetupGeography.objects.get(area_id=subcounty.parent_area_id)

    # orgunit = RegPersonsOrgUnits.objects.get(person=child)
    form = CparaAssessment()
    ovc_id = int(id)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)

    # pdb.set_trace()  
    # PAST CPARA
    
    past_cpara = []
    cpara_events = OVCCareEvents.objects.filter(event_type_id='cpr', person_id=id, is_void=False)
    if cpara_events:
        for one_cpara_event in cpara_events:
            event_detail = ""
            total_benchmark_score = 0
            # cpara_data = OVCCareCpara.objects.filter(event=one_cpara_event)
            cpara_data = OVCCareBenchmarkScore.objects.filter(event_id=one_cpara_event.event)
            bm_array = []
            if cpara_data:
                for one_cpara_bench in cpara_data:
                    bm_array.append("Yes" if one_cpara_bench.benchmark_1 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_2 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_3 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_4 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_5 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_6 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_7 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_8 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_9 == 1 else "No")

                    
                    benchmark_1 = "Benchmark 1: (Yes)" if one_cpara_bench.benchmark_1 == 1 else "Benchmark 1: (No)"
                    benchmark_2 = "Benchmark 2: (Yes)" if one_cpara_bench.benchmark_2 == 1 else "Benchmark 2: (No)"
                    benchmark_3 = "Benchmark 3: (Yes)" if one_cpara_bench.benchmark_3 == 1 else "Benchmark 3: (No)"
                    benchmark_4 = "Benchmark 4: (Yes)" if one_cpara_bench.benchmark_4 == 1 else "Benchmark 4: (No)"
                    benchmark_5 = "Benchmark 5: (Yes)" if one_cpara_bench.benchmark_5 == 1 else "Benchmark 5: (No)"
                    benchmark_6 = "Benchmark 6: (Yes)" if one_cpara_bench.benchmark_6 == 1 else "Benchmark 6: (No)"
                    benchmark_7 = "Benchmark 7: (Yes)" if one_cpara_bench.benchmark_7 == 1 else "Benchmark 7: (No)"
                    benchmark_8 = "Benchmark 8: (Yes)" if one_cpara_bench.benchmark_8 == 1 else "Benchmark 8: (No)"
                    benchmark_9 = "Benchmark 9: (Yes)" if one_cpara_bench.benchmark_9 == 1 else "Benchmark 9: (No)"

                    str_1 = benchmark_1 + ", " + benchmark_2 + ", " + benchmark_3 + ", " + benchmark_4 + ", " + benchmark_5 + ", "
                    str_2 = benchmark_6 + ", " + benchmark_7 + ", " + benchmark_8 + ", " + benchmark_9 + ", "
                    

                    total_benchmark_score = int(one_cpara_bench.benchmark_1) + int(one_cpara_bench.benchmark_2) + int(
                        one_cpara_bench.benchmark_3) + int(one_cpara_bench.benchmark_4) + int(
                        one_cpara_bench.benchmark_5) + int(one_cpara_bench.benchmark_6) + int(
                        one_cpara_bench.benchmark_7) + int(one_cpara_bench.benchmark_8) + int(
                        one_cpara_bench.benchmark_9) 
                        
                    full_str = str_1 + str_2 # + str_3 + str_4
                    event_detail = event_detail + full_str
            else:
                event_detail = "No answered questions found"
                total_benchmark_score = 0
                bm_array = []
            past_cpara.append({
                'ev_date': one_cpara_event.date_of_event,
                'ev_person': child.id,
                'ev_type': 'CPARA',
                'ev_id': str(one_cpara_event.pk),
                'ev_detail': str(event_detail),
                'ev_score': total_benchmark_score,
                'bm_array': bm_array
            })

            
    context = {'form':form,
                'person': id,
                'hhmembers': hhmembers,
                'child': child,
                'creg': creg,
                'caregiver': care_giver,
                'household': house_hold,
                'ward': ward,
                'subcounty': subcounty,
                'county': county,
                'care_giver': care_giver,
                'past_cpara': past_cpara
                
                }    
    return render(request,'forms/new_cpara.html',context)



# Update cpara edit functionality
def edit_cpara(request, id):    
    if request.method == 'POST':
        
        data = request.POST
        
        update_time=timezone.now()
        ovc_event = OVCCareEvents.objects.filter(event=id)
        date_of_event = data.get('d_o_a')
        cpara_saved = OVCCareCpara.objects.filter(event=id)     

        ovc_score = data.get('bench_array').replace('[', '').replace(']', '').split(',')

        # Update OVC CPARA Table
        try:
            for question in cpara_saved:
                answer=data.get(question.question_code)

                answer_value = {
                    'AYES':'True',
                    'ANNO':'False',
                    'ANA':'Na',
                    None:'No'
                }

                answer = answer_value[answer]
                # print(f'{question.question_code}  <><>  {answer}')
                OVCCareCpara.objects.filter(event=id,question_code = question.question_code).update(                    
                    answer=answer,
                    date_of_event=date_of_event,
                    timestamp_updated=update_time,  
                    event=id
                )
                
                print(OVCCareCpara.objects.filter(question_code=question.question_code, event=id))
                
                
        except Exception as e:
            print(f'The table OVC Cpara didnt update: {e} ')

    
        # Update OVC Benchmark Score Table
        try:
            OVCCareBenchmarkScore.objects.filter(event=id).update(
                benchmark_1=int(ovc_score[0]),
                benchmark_2=int(ovc_score[1]),
                benchmark_3=int(ovc_score[2]),
                benchmark_4=int(ovc_score[3]),
                benchmark_5=int(ovc_score[4]),
                benchmark_6=int(ovc_score[5]),
                benchmark_7=int(ovc_score[6]),
                benchmark_8=int(ovc_score[7]),
                benchmark_9=int(ovc_score[8]),
                score=sum([int(i) for i in ovc_score]),
                timestamp_updated=update_time
            )
        except Exception as e:
            msg1 = f"Error while updating to ovccarebenchmark: {e}" 
        
        person_id = OVCCareEvents.objects.filter(event=id)[0].person_id
        

        sub_pop = {'CP6d_1':'double','CP6d_2':'AGYW','CP6d_3':'HEI','CP6d_4':'FSW','CP6d_5':'PLHIV','CP6d_6':'CLHIV','CP6d_7':'SVAC','CP6d_8':'AHIV'}
     
        # Update OVC Sub Popuplation Table
        try:
            for q, v in sub_pop.items():
                if data.get(q) == 'on':
                    OVCSubPopulation.objects.filter(event=id, criteria=v,person=person_id).update_or_create(
                        criteria=v,
                        date_of_event=date_of_event,
                        timestamp_updated = update_time,
                        event=OVCCareEvents.objects.filter(event=id),
                        timestamp_created=update_time,
                        person=RegPerson.objects.filter(person_id)
                    )
        except Exception as e:
            print(e)
            msg = f'Error while updating to OVC sub population. Send this error to Support'

        url = reverse('ovc_view', kwargs={'id':person_id})
        msg = 'CPARA edited successfully'
        messages.add_message(request, messages.INFO, msg)
        return HttpResponseRedirect(url)

        # cpara_id=OVCCareCpara.objects.get(event=id,is_void=False)
    # person_id=OVCSubPopulation.objects.filter(event=id).first().person_id
    # house_id = OVCHHMembers.objects.get(person_id=person_id).house_hold_id
    # person_id = OVCHHMembers.objects.get(house_hold=house_id, member_type='TOVC').person_id
    # pdb.set_trace()
    person_id = OVCCareCpara.objects.filter(event=id).first().person_id

    
    cpara_data=OVCCareCpara.objects.filter(event=id,is_void=False).values()

    # Get an event date of a single question for that event id
    evts = OVCCareCpara.objects.filter(event_id=id) #.first()
    d_o_a=OVCCareCpara.objects.get(event=id, question_code='CP10q').date_of_event
    CP2d=OVCCareCpara.objects.get(event=id, question_code='CP10q').date_of_previous_event
    # date_event = cpara_data.get('date_of_event')
   
    # pull OVC sub population get
    ovc_sub_pop_data = {}    
    ovc_sub_population = OVCSubPopulation.objects.filter(event=id,is_void=False).values()
    # OVCSubPopulation.objects.filter(event=id,is_void=False).delete()
    sub_pop = {'double' :'CP6d_1','AGYW':'CP6d_2','HEI':'CP6d_3','FSW':'CP6d_4','PLHIV':'CP6d_5','CLHIV':'CP6d_6','SVAC':'CP6d_7','AHIV':'CP6d_8'}
    for ovc_sub in ovc_sub_population:
        
        ovc_sub_id = ovc_sub['person_id']
        if ovc_sub_id == person_id:
            ovc_sub_q = ovc_sub.get('criteria')
            ovc_sub_pop_data[sub_pop[ovc_sub_q]] = 'on'
        else:
            ovc_sub_q = ovc_sub.get('criteria')
            ovc_sub_pop_data[str(ovc_sub_id)+'_'+sub_pop[ovc_sub_q]] = 'on'

    
    # cpara = cpara_id.values_list()
    edit_data_cpara={}
    answer_value={
        'False': 'ANNO',
        'True': 'AYES',
        'Na': 'ANA',
        'No':'',
        'AYES':'AYES'
    }

    for one_data in cpara_data:
        one_data_q = one_data.get('question_code')
        one_data_a = one_data.get('answer') 
        if one_data_q == 'CP2d':
            one_data_a
            edit_data_cpara[one_data_q]=one_data_a
        else:
            # one_data_val = answer_value[one_data_a]            
            edit_data_cpara[one_data_q]=answer_value[one_data_a]
    
    # edit_data_cpara['d_o_a'] = date_event
    edit_data_cpara.update(ovc_sub_pop_data)
    edit_data_cpara['d_o_a']=d_o_a
    edit_data_cpara['CP2d']=CP2d

    individual_cpara_data = {}

    individual_cpara = OVCCareIndividaulCpara.objects.filter(event=id, answer=True)
    for one_individual_cpara in individual_cpara:
        question_s = str(one_individual_cpara.person.id) + '_' + (one_individual_cpara.question_code)
        answer = one_individual_cpara.answer
        if answer == True:
            answer = 'AYES'
        else:
            answer = 'ANNO'
                
        individual_cpara_data[question_s] = answer

    # breakpoint()
    # person_id=OVCSubPopulation.objects.filter(event=id).first().person_id
    # house_id = OVCHHMembers.objects.get(person_id=person_id).house_hold_id
    # person_id = OVCHHMembers.objects.get(house_hold=house_id, member_type='TOVC').person_id
    person_id = OVCCareCpara.objects.filter(event=id).first().person_id

    child = RegPerson.objects.get(id=person_id)
    guardians = RegPersonsGuardians.objects.select_related().filter(
        child_person=child, is_void=False, date_delinked=None)
    siblings = RegPersonsSiblings.objects.select_related().filter(
        child_person=child, is_void=False, date_delinked=None)
    # Reverse relationship
    osiblings = RegPersonsSiblings.objects.select_related().filter(
        sibling_person=child, is_void=False, date_delinked=None)
    oguardians = RegPersonsGuardians.objects.select_related().filter(
        guardian_person=child, is_void=False, date_delinked=None)
    # child = RegPerson.objects.get(id=id)
    ovc_id = int(person_id)
    creg = OVCRegistration.objects.get(is_void=False, person_id=ovc_id)

    
    # Get house hold
    hhold = OVCHHMembers.objects.get(is_void=False, person_id=person_id)
    # Get HH members
    hhid = hhold.house_hold_id
    hhmqs = OVCHHMembers.objects.filter(is_void=False, house_hold_id=hhid).order_by("-hh_head")
    hhmembers2 = hhmqs.exclude(person_id=person_id)
    
    # Get child geo
    child_geos = RegPersonsGeo.objects.select_related().filter(
        person=person_id, is_void=False, date_delinked=None)
    all_geos_county, all_geos_wards, all_geos = [], [], []
    for person_geo in child_geos:
        geo_name = str(person_geo.area.area_id)
        geo_type = person_geo.area.area_type_id
        if geo_type == 'GPRV':
            all_geos_county.append(geo_name)
        elif geo_type == 'GDIS':
            all_geos.append(geo_name)
        else:
            all_geos_wards.append(geo_name)
    if all_geos:
        geos = ', '.join(all_geos)
    else:
        geos = None
    if all_geos_wards:
        geo_wards = ', '.join(all_geos_wards)
    else:
        geo_wards = None
    if all_geos_county:
        geo_county = ', '.join(all_geos_county)
    # geo_wards = geo_wards

    # geo_wards = geo_wards
    if geo_wards is None:
        ward = None
        subcounty = None
        county = None
    else:
        ward_id = int(geo_wards)
        ward = SetupGeography.objects.get(area_id=ward_id)
        subcounty = SetupGeography.objects.get(area_id=ward.parent_area_id)
        county = SetupGeography.objects.get(area_id=subcounty.parent_area_id)


    # PAST CPARA
    past_cpara = []
    cpara_events = OVCCareEvents.objects.filter(event_type_id='cpr', person_id=child.id)
    if cpara_events:
        for one_cpara_event in cpara_events:
            event_detail = ""
            total_benchmark_score = 0
            # cpara_data = OVCCareCpara.objects.filter(event=one_cpara_event)
            cpara_data = OVCCareBenchmarkScore.objects.filter(event_id=one_cpara_event.event)
            bm_array = []
            if cpara_data:
                for one_cpara_bench in cpara_data:
                    bm_array.append("Yes" if one_cpara_bench.benchmark_1 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_2 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_3 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_4 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_5 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_6 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_7 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_8 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_9 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_10 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_11 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_12 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_13 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_14 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_15 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_16 == 1 else "No")
                    bm_array.append("Yes" if one_cpara_bench.benchmark_17 == 1 else "No")
                    
                    benchmark_1 = "Benchmark 1: (Yes)" if one_cpara_bench.benchmark_1 == 1 else "Benchmark 1: (No)"
                    benchmark_2 = "Benchmark 2: (Yes)" if one_cpara_bench.benchmark_2 == 1 else "Benchmark 2: (No)"
                    benchmark_3 = "Benchmark 3: (Yes)" if one_cpara_bench.benchmark_3 == 1 else "Benchmark 3: (No)"
                    benchmark_4 = "Benchmark 4: (Yes)" if one_cpara_bench.benchmark_4 == 1 else "Benchmark 4: (No)"
                    benchmark_5 = "Benchmark 5: (Yes)" if one_cpara_bench.benchmark_5 == 1 else "Benchmark 5: (No)"
                    benchmark_6 = "Benchmark 6: (Yes)" if one_cpara_bench.benchmark_6 == 1 else "Benchmark 6: (No)"
                    benchmark_7 = "Benchmark 7: (Yes)" if one_cpara_bench.benchmark_7 == 1 else "Benchmark 7: (No)"
                    benchmark_8 = "Benchmark 8: (Yes)" if one_cpara_bench.benchmark_8 == 1 else "Benchmark 8: (No)"
                    benchmark_9 = "Benchmark 9: (Yes)" if one_cpara_bench.benchmark_9 == 1 else "Benchmark 9: (No)"
                    benchmark_10 = "Benchmark 10: (Yes)" if one_cpara_bench.benchmark_10 == 1 else "Benchmark 10: (No)"
                    benchmark_11 = "Benchmark 11: (Yes)" if one_cpara_bench.benchmark_11 == 1 else "Benchmark 11: (No)"
                    benchmark_12 = "Benchmark 12: (Yes)" if one_cpara_bench.benchmark_12 == 1 else "Benchmark 12: (No)"
                    benchmark_13 = "Benchmark 13: (Yes)" if one_cpara_bench.benchmark_13 == 1 else "Benchmark 13: (No)"
                    benchmark_14 = "Benchmark 14: (Yes)" if one_cpara_bench.benchmark_14 == 1 else "Benchmark 14: (No)"
                    benchmark_15 = "Benchmark 15: (Yes)" if one_cpara_bench.benchmark_15 == 1 else "Benchmark 15: (No)"
                    benchmark_16 = "Benchmark 16: (Yes)" if one_cpara_bench.benchmark_16 == 1 else "Benchmark 16: (No)"
                    benchmark_17 = "Benchmark 17: (Yes)" if one_cpara_bench.benchmark_17 == 1 else "Benchmark 17: (No)"

                    str_1 = benchmark_1 + ", " + benchmark_2 + ", " + benchmark_3 + ", " + benchmark_4 + ", " + benchmark_5 + ", "
                    str_2 = benchmark_6 + ", " + benchmark_7 + ", " + benchmark_8 + ", " + benchmark_9 + ", "
                    str_3 = benchmark_10 + ", " + benchmark_11 + ", " + benchmark_12 + ", " + benchmark_13 + ", "
                    str_4 = benchmark_14 + ", " + benchmark_15 + ", " + benchmark_16 + ", " + benchmark_17

                    total_benchmark_score = int(one_cpara_bench.benchmark_1) + int(one_cpara_bench.benchmark_2) + int(
                        one_cpara_bench.benchmark_3) + int(one_cpara_bench.benchmark_4) + int(
                        one_cpara_bench.benchmark_5) + int(one_cpara_bench.benchmark_6) + int(
                        one_cpara_bench.benchmark_7) + int(one_cpara_bench.benchmark_8) + int(
                        one_cpara_bench.benchmark_9) + int(one_cpara_bench.benchmark_10) + int(
                        one_cpara_bench.benchmark_11) + int(one_cpara_bench.benchmark_12) + int(
                        one_cpara_bench.benchmark_13) + int(one_cpara_bench.benchmark_14) + int(
                        one_cpara_bench.benchmark_15) + int(one_cpara_bench.benchmark_16) + int(
                        one_cpara_bench.benchmark_17)
                    full_str = str_1 + str_2 + str_3 + str_4
                    # qn_string = str(one_cpara_bench.question_code) + " (" + str(one_cpara_bench.answer) + "), "
                    event_detail = event_detail + full_str
            else:
                event_detail = "No answered questions found"
                total_benchmark_score = 0
                bm_array = []
            past_cpara.append({
                'ev_date': one_cpara_event.date_of_event,
                'ev_person': child.id,
                'ev_type': 'CPARA',
                'ev_id': str(one_cpara_event.pk),
                'ev_detail': str(event_detail),
                'ev_score': total_benchmark_score,
                'bm_array': bm_array
            })

            

    # print(f'Edit data: {edit_data_cpara}')
    
    ovc_id = int(person_id)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
    hhmembers = hhmembers2.exclude(person=care_giver)   

    form = CparaAssessment(data=edit_data_cpara)
    context = {'form':form,
                'person': id,
                'siblings': siblings,
                'hhmembers': hhmembers,
                'osiblings': osiblings,
                'oguardians': oguardians,
                'child': child,
                'creg': creg,
                'caregiver': care_giver,
                # 'household': house_hold,
                'ward': ward,
                'subcounty': subcounty,
                'county': county,
                'care_giver': care_giver,
                'sub_pop':ovc_sub_pop_data,
                'ind_cpara_data':individual_cpara_data
                
                }

    return render(request,'forms/edit_new_cpara.html',context)
    

# Delete Cpara functionality
def delete_cpara(request, id, btn_event_pk):
    jsonCPARAData = []
    msg = ''

    try:
        # event_id = uuid.UUID(btn_event_pk)
        event_id = btn_event_pk
        d_event = OVCCareEvents.objects.filter(pk=event_id)[0].timestamp_created
        # pdb.set_trace()
        delta = get_days_difference(d_event)
        if delta < 90:
            # Event Instance
            del_event = OVCCareEvents.objects.get(pk=event_id)
            # Event object
            event_to_del = OVCCareEvents.objects.filter(pk=event_id)
            # print ("event: {}".format(type(del_event)))
         
            # import pdb
            if del_event:
                # delete cpara
                ovcpara = OVCCareCpara.objects.filter(event=del_event)
                ovc_bench = OVCCareBenchmarkScore.objects.filter(event=del_event)
                ovc_sub = OVCSubPopulation.objects.filter(event=del_event)
                ovc_ind = OVCCareIndividaulCpara.objects.filter(event=del_event)
                # pdb.set_trace()
                if ovcpara:                    
                    ovcpara.update(is_void=True)
                    msg1 = "OVC Cpara Deleted successfully"
              
                    event_to_del.update(is_void=True)  
                    msg2 = "OVC Event Deleted successfully"

                    ovc_bench.update(is_void=True)
                    msg3 = "Benchmark Score deleted successfuly"

                    ovc_sub.update(is_void=True)
                    msg4 = "OVC sub population deleted successfuly"

                    ovc_ind.update(is_void=True)
                    msg5 = "OVC individual deleted successfuly"

                    messages = " ".join(msg1, msg2, msg3, msg4, msg5)

        else:
            msg = "Can't delete after 90 days"
    except Exception as e:
        msg = 'An error occured : %s' % str(e)
        print(str(e))
    jsonCPARAData.append({'msg': msg})
    return JsonResponse(jsonCPARAData,
                        content_type='application/json',
                        safe=False)


def grad_monitor_tool(request, id):
    if request.method == 'POST':
        data = request.POST
        # print(data)

        child = RegPerson.objects.get(id=id)       
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
        caregiver_id = OVCRegistration.objects.get(person=child).caretaker_id
        caregiver = RegPerson.objects.get(id=caregiver_id)
 
        event_date = convert_date(data.get('gm1d'))
        event_type_id = 'obm'
        time_saved = timezone.now()

        event_counter = OVCCareEvents.objects.filter(
            event_type_id=event_type_id, person=id, is_void=False).count()

        # SAVE EVENT
        try:
            ovccareevent = OVCCareEvents.objects.create(
                event_type_id=event_type_id,
                event_counter=event_counter,
                event_score=0,
                created_by=request.user.id,
                person=RegPerson.objects.get(pk=int(id)),
                house_hold=house_hold
            )
        except Exception as e:
            error_message = f'Events didn\'t save : {e}'
            print(error_message)
       
        answer_value = {
            'AYES': True,
            'ANNO': False
        }
        try:
            OVCBenchmarkMonitoring.objects.create(
                household=house_hold,
                # person=child,
                caregiver=caregiver,
                form_type=data.get('form1_type'),
                benchmark1=answer_value[data.get('cm2q')],
                benchmark2=answer_value[data.get('cm3q')],
                benchmark3=answer_value[data.get('cm4q')],
                benchmark4=answer_value[data.get('cm5q')],
                benchmark5=answer_value[data.get('cm6q')],
                benchmark6=answer_value[data.get('cm7q')],
                benchmark7=answer_value[data.get('cm8q')],
                benchmark8=answer_value[data.get('cm9q')],
                benchmark9=answer_value[data.get('cm10q')],
                succesful_exit_checked =answer_value[data.get('cm13q')],
                case_closure_checked=answer_value[data.get('cm14q')],
                event_date=event_date,
                event=ovccareevent,
                timestamp_created=time_saved
            )

        except Exception as e:
            error_message = 'error saving graduation monitoring tool - %s' % (str(e))
            messages.add_message(request, messages.INFO, error_message)

        msg = 'Graduation Monitoring saved successful'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id': id})
        return HttpResponseRedirect(url)        

    else:
        
        ovc_id = int(id)
        child = RegPerson.objects.get(is_void=False, id=ovc_id)        
        care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
        creg = OVCRegistration.objects.get(is_void=False, person_id=ovc_id)
        caregiver_id = OVCRegistration.objects.get(person=child).caretaker_id
        caregiver = RegPerson.objects.get(id=caregiver_id)
        house_hold = OVCHouseHold.objects.get(id=OVCHHMembers.objects.get(person=child).house_hold_id)
        
        # Show previous cpara monitoring events
        event = OVCCareEvents.objects.filter(person_id=ovc_id).values_list('event')
        
        try:
            
            benchmark_data = OVCBenchmarkMonitoring.objects.filter(is_void=False, household=house_hold)   #filter(event=event).order_by('event_date'))
        except Exception as e:
            benchmark_data = {}
            print(e)
        
        form = gradMonitoringToolform()
             
        context = {
            'form': form, 
            'care_giver': care_giver,
            'creg':creg,
            'child':child,
            'ovc_id':ovc_id,
            'caregiver':caregiver,
            'benchmark_data': benchmark_data
            }
        
        return render(request, 'forms/new_grad_monitor_tool.html',context)

def delete_benchmark(request, id):
    ovc_bench = OVCBenchmarkMonitoring.objects.filter(obm_id=id)

    # Gets the instance
    household1 =OVCBenchmarkMonitoring.objects.get(obm_id=id)
    re_person = OVCHHMembers.objects.filter(house_hold=household1.household, hh_head=False).first().person.id
    
    ovc_bench.update(is_void=True)
    url = reverse('ovc_view', kwargs={'id':re_person})
    msg=f"Event id: {id} deleted successfully"
    messages.add_message(request, messages.WARNING, msg)
    return HttpResponseRedirect(url)    

    
def edit_grad_monitor(request, id):
    if request.method=='POST':
        data=request.POST
        answer_value = {
            'AYES': True,
            'ANNO': False
        }

        event_date = convert_date(data.get('gm1d'))
        time_updated = timezone.now()
        household1 =OVCBenchmarkMonitoring.objects.get(obm_id=id)
        re_person = OVCHHMembers.objects.filter(house_hold=household1.household, hh_head=False, member_type = 'TOVC').first().person.id
        
        try:
            OVCBenchmarkMonitoring.objects.filter(obm_id=id).update(
                    benchmark1=answer_value[data.get('cm2q')],
                    benchmark2=answer_value[data.get('cm3q')],
                    benchmark3=answer_value[data.get('cm4q')],
                    benchmark4=answer_value[data.get('cm5q')],
                    benchmark5=answer_value[data.get('cm6q')],
                    benchmark6=answer_value[data.get('cm7q')],
                    benchmark7=answer_value[data.get('cm8q')],
                    benchmark8=answer_value[data.get('cm9q')],
                    benchmark9=answer_value[data.get('cm10q')],
                    succesful_exit_checked =answer_value[data.get('cm13q')],
                    case_closure_checked=answer_value[data.get('cm14q')],
                    event_date=event_date,
                    timestamp_updated = time_updated,
                    
                )         
           
            
        except Exception as e:
            print(f'{e}')

        msg = 'Graduation Monitoring edit saved successful'
        messages.add_message(request, messages.INFO, msg)
        url = reverse('ovc_view', kwargs={'id':re_person})
        return HttpResponseRedirect(url)
    
    # Get Method to pick the values of edit form
    # try:
    data_db = OVCBenchmarkMonitoring.objects.filter(obm_id=id).values()
    def map_yes_no(value):
        if value==True:
            return 'AYES'
        else:
            return 'ANNO'

    edit_data= {
        'gm1d': data_db[0]['event_date'].strftime("%Y-%m-%d"),
        'cm2q': map_yes_no(data_db[0]['benchmark1']),
        'cm3q': map_yes_no(data_db[0]['benchmark2']),
        'cm4q': map_yes_no(data_db[0]['benchmark3']),
        'cm5q': map_yes_no(data_db[0]['benchmark4']),
        'cm6q': map_yes_no(data_db[0]['benchmark5']),
        'cm7q': map_yes_no(data_db[0]['benchmark6']),
        'cm8q': map_yes_no(data_db[0]['benchmark7']),
        'cm9q': map_yes_no(data_db[0]['benchmark8']),
        'cm10q': map_yes_no(data_db[0]['benchmark9']),
        'cm13q': map_yes_no(data_db[0]['succesful_exit_checked']),
        'cm14q': map_yes_no(data_db[0]['case_closure_checked'])
        }
        
        
    # except Exception as e:
    #     print(f'The error is: {e}')

    form = gradMonitoringToolform(data=edit_data)
    
    household1 =OVCBenchmarkMonitoring.objects.get(obm_id=id)
    re_person = OVCHHMembers.objects.filter(house_hold=household1.household, hh_head=False).first().person.id
    
    ovc_id = int(re_person)
    child = RegPerson.objects.get(is_void=False, id=ovc_id)
    care_giver = RegPerson.objects.get(id=OVCRegistration.objects.get(person=child).caretaker_id)
    creg = OVCRegistration.objects.get(is_void=False, person_id=ovc_id)
    caregiver_id = OVCRegistration.objects.get(person=child).caretaker_id
    caregiver = RegPerson.objects.get(id=caregiver_id)
    form_type = OVCBenchmarkMonitoring.objects.filter(obm_id=id,is_void=False).values_list()[0][3]
    
    if form_type == 'bm':
        form_type = 'Benchmark Monitoring'
    else:
        form_type = 'Households Reaching Case Plan Achievement'
    
    context = {'form':form,
            'status': 200,
            'care_giver': care_giver,
            'creg':creg,
            'caregiver':caregiver,
            'form_type':form_type
                    }
        
    return render(request, 'forms/edit_grad_monitor_tool.html', context)


def get_org(request, name):
    org_unit_detail = get_list_of_org_units(name)
    return render(
        request,
        template_name='forms/case_transfer.html',
        context={
            'org_unit_detail': org_unit_detail
        }
    )


def case_transfer(request, id):
    try:
        import pdb
        init_data = RegPerson.objects.filter(pk=id)
        child = RegPerson.objects.get(id=id)
        care_giver = RegPerson.objects.get(
            id=OVCRegistration.objects.get(person=child).caretaker_id)
        house_hold = OVCHouseHold.objects.get(
            id=OVCHHMembers.objects.get(person=child).house_hold_id)

        siblings = RegPersonsSiblings.objects.select_related().filter(
            child_person=id, is_void=False, date_delinked=None)
        hhold = OVCHHMembers.objects.get(
            is_void=False, person_id=child.id)
        # Get HH members
        hhid = hhold.house_hold_id
        hhmembers = OVCHHMembers.objects.filter(
            is_void=False, house_hold_id=hhid)
        if request.method == 'POST':
            print(request.POST)
            event_id = 'FCSI'
            person_id = int(id)
            date_of_transfer = request.POST.get("TRANSFER_DATE")
            hhmembers_check = request.POST.getlist('member_id_check')
            hhmembers = request.POST.getlist('member_id')

            event_counter = OVCCareEvents.objects.filter(
                event_type_id=event_id, person=id, is_void=False).count()

            ovccareevent = OVCCareEvents(
                event_type_id=event_id,
                event_counter=event_counter,
                event_score=0,
                date_of_event=date_of_transfer,
                created_by=request.user.id,
                person_id=person_id,
                date_of_previous_event='2022-01-01',
                house_hold=house_hold
            )

            ovccareevent.save()
            event_id = ovccareevent.pk

            organization = RegOrgUnit.objects.order_by('org_unit_name')[0]
            org_unit_id = organization.id

            for hhmember in hhmembers:
                print("hhmember", hhmember)
                index = hhmembers_check.index(hhmember)
                reason = str(request.POST.getlist("REASON")[index]),
                date_follow_up = str(request.POST.getlist("FOLLOW_UP_DATE")[index])
                print(index, id, event_id, house_hold,date_of_transfer,
                      reason, date_follow_up, 'tttt')

                OVCCareTransfer(
                    person_id=person_id,
                    event_id=event_id,
                    household=house_hold,
                    rec_organization_id=org_unit_id,
                    date_of_event=date_of_transfer,
                    reason=reason,
                    date_follow_up=date_follow_up,
                    date_of_transfer=date_of_transfer
                ).save()
            return redirect(reverse(ovc_view, kwargs={'id': person_id}))
        else:
            caseTransferForm = CaseTransferForm()            
            return render(
                request,
                template_name=
                    'forms/case_transfer.html',
                context={
                    'case_transfer_form' : caseTransferForm,
                    'init_data': init_data,
                    'siblings':siblings,
                    'care_giver': care_giver, 
                    'child':child,
                    'house_hold': house_hold,
                    'hhid':hhid,
                    'hhmembers':hhmembers,
                    }
            )
    except Exception as e:
        raise e
    else:
        pass
