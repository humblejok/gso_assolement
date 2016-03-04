# Create your views here.
from django.shortcuts import render
from django.http.response import HttpResponse
from seq_common.utils.classes import my_class_import
from json import dumps, loads
from django.forms.models import model_to_dict
import datetime
from assolement import utils
import traceback
from django.contrib.auth.decorators import login_required
from assolement.models import Crop, SoilKind, SoilPosition, Parcel, Rotation

def clean_post_value(value):
    if isinstance(value, list) and len(value)==1:
        return value[0]
    else:
        return value
    
def quick_dict(entity_class, entity):
    json_dict = {}
    for field_info in entity_class._meta.fields:
        if hasattr(entity, field_info.name):
            json_dict[field_info.name] = getattr(entity, field_info.name)
    return json_dict

def dict_to_json_compliance(data, data_type=None):
    if data_type!=None and not hasattr(data_type, '_meta'):
        data_type = None
    if isinstance(data, datetime.date):
        new_data = data.strftime('%Y-%m-%d')
    elif isinstance(data, datetime.datetime):
        new_data = data.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(data, dict):
        new_data = {}
        for key in data.keys():
            key = str(key)
            if data_type==None:
                new_data[key] = dict_to_json_compliance(data[key], data_type)
            else:
                if data_type._meta.get_field(key).get_internal_type()=='ForeignKey' and data[key]!=None:
                    foreign_class = data_type._meta.get_field(key).rel.to
                    new_data[key] = dict_to_json_compliance(model_to_dict(foreign_class.objects.get(id=data[key])))
                elif data_type._meta.get_field(key).get_internal_type()=='ManyToManyField':
                    foreign_class = data_type._meta.get_field(key).rel.to
                    new_data[key] = [dict_to_json_compliance(model_to_dict(foreign_class.objects.get(id=item))) for item in data[key]]
                else:
                    new_data[key] = dict_to_json_compliance(data[key])
    elif isinstance(data, list):
        new_data = [dict_to_json_compliance(item, data_type) for item in data]
    else:
        return data
    return new_data

@login_required
def index(request):
    crops = dumps([dict_to_json_compliance(model_to_dict(crop), Crop) for crop in Crop.objects.filter(user__id=request.user.id).order_by('name')])
    soil_kinds = dumps([dict_to_json_compliance(model_to_dict(soil_kind), SoilKind) for soil_kind in SoilKind.objects.filter(user__id=request.user.id).order_by('number')])
    soil_positions = dumps([dict_to_json_compliance(model_to_dict(soil_position), SoilPosition) for soil_position in SoilPosition.objects.filter(user__id=request.user.id).order_by('code')])
    parcels = dumps([dict_to_json_compliance(model_to_dict(parcel), Parcel) for parcel in Parcel.objects.filter(user__id=request.user.id).order_by('name')])
    context = {'soils_kinds': soil_kinds,
               'soil_positions': soil_positions,
               'crops': crops,
               'parcel': parcels}
    return render(request, 'index.html', context)

def compute_year(request):
    if 'year' not in request.POST:
        json_response = {'success': False, 'message': 'Calcul assolement: Un argument est manquant dans l''appel au serveur.'}
    else:
        year = int(clean_post_value(request.POST['year']))
        solutions = utils.assolement_computer(year, request.user)
        json_response = {'success': True, 'solutions': solutions}
    return HttpResponse(dumps(json_response),"json")

def update_history(request):
    if 'history' not in request.POST:
        json_response = {'success': False, 'message': 'Sauvegarde historique: Un argument est manquant dans l''appel au serveur.'}
    else:
        try:
            history = loads(request.POST['history'])
            for key in history:
                ids = key.split('-')
                parcel = Parcel.objects.get(id=ids[1])
                rotation = parcel.historique.filter(rotation=ids[2])
                if rotation.exists():
                    rotation = rotation[0]
                    if history[key]==-1:
                        parcel.historique.remove(rotation)
                        parcel.save()
                        rotation.delete()
                    else:
                        rotation.crop = Crop.objects.get(id=history[key])
                elif not rotation.exists() and history[key]!=-1:
                    rotation = Rotation()
                    rotation.year = ids[2]
                    rotation.crop = Crop.objects.get(id=history[key])
                    rotation.save()
                    parcel.historique.add(rotation)
            parcels = [dict_to_json_compliance(model_to_dict(parcel), Parcel) for parcel in Parcel.objects.all().order_by('name')]
            json_response = {'success': True, 'updated_values': parcels}
        except:
            json_response = {'success': False, 'message': 'Sauvegarde historique: La mise a jour a echoue lors de la sauvergarde en base de donnees.'}
    return HttpResponse(dumps(json_response),"json")

def remove(request):
    if 'target_class' not in request.POST or 'prefix' not in request.POST or 'id' not in request.POST:
        json_response = {'success': False, 'message': 'Suppression: Un argument est manquant dans l''appel au serveur.'}
    else:
        target_class = clean_post_value(request.POST['target_class'])
        try:
            target_class = my_class_import(target_class)
            prefix = clean_post_value(request.POST['prefix'])
            entity_id = clean_post_value(request.POST['id'])
            entity = target_class.objects.get(id=entity_id)
            json_response = {'success': True, 'prefix': prefix, 'value': dict_to_json_compliance(model_to_dict(entity), target_class)}
            entity.delete()
        except:
            json_response = {'success': False, 'message': 'Suppression: L''objet avec l''identifiant [' + entity_id + '] et le type [' + str(target_class) + '] n'' a pas ete trouve dans la base de donnees.' }

    return HttpResponse(dumps(json_response),"json")

def create_update(request):
    if 'target_class' not in request.POST or 'prefix' not in request.POST or 'id' not in request.POST:
        json_response = {'success': False, 'message': 'Mise a jour: Un argument est manquant dans l''appel au serveur.'}
    else:
        try:
            target_class = clean_post_value(request.POST['target_class'])
            target_class = my_class_import(target_class)
            prefix = clean_post_value(request.POST['prefix'])
            if 'id' in request.POST and request.POST['id']!=None and request.POST['id']!='':
                entity_id = clean_post_value(request.POST['id'])
                entity = target_class.objects.get(id=entity_id)
                update = True
            else:
                entity = target_class()
                entity.user = request.user
                update = False
            for field in target_class._meta.fields:
                if field.name in request.POST and field.name!='id' and field.__class__.__name__!="BooleanField":
                    if field.__class__.__name__=="ForeignKey":
                        setattr(entity, field.name, field.rel.to.objects.get(id=request.POST[field.name]))
                    elif field.__class__.__name__=="FloatField":
                        setattr(entity, field.name, float(clean_post_value(request.POST[field.name]).replace(',', '.').replace('%', '')))
                    else:
                        setattr(entity, field.name, clean_post_value(request.POST[field.name]))
                elif field.__class__.__name__=="BooleanField":
                    if field.name in request.POST and request.POST[field.name].lower() in ['on','true']:
                        setattr(entity, field.name, True)
                    else:
                        setattr(entity, field.name, False)
            # Pre-saving for M2M links
            entity.save()
            for field in target_class._meta.many_to_many:
                getattr(entity, field.name).clear()
                if field.name in request.POST: 
                    for sub_id in request.POST[field.name].split(','):
                        getattr(entity, field.name).add(field.rel.to.objects.get(id=sub_id))
            entity.save()
            json_response = {'success': True, 'update': update, 'prefix': prefix, 'value': dict_to_json_compliance(model_to_dict(entity), target_class)}
        except:
            traceback.print_exc()
            json_response = {'success': False, 'message': 'Mise a jour: L''objet avec l''identifiant [' + entity_id + '] et le type [' + str(target_class) + '] n'' a pas ete trouve dans la base de donnees.' }
    return HttpResponse(dumps(json_response),"json")