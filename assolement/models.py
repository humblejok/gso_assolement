from django.db import models
from django.contrib.auth.models import User



class SoilKind(models.Model):
    user = models.ForeignKey(User, null=False)
    number = models.IntegerField()
    name = models.CharField(max_length=128)
    
class SoilPosition(models.Model):
    user = models.ForeignKey(User, null=False)
    code = models.CharField(max_length=1)
    name = models.CharField(max_length=128)

class Crop(models.Model):
    user = models.ForeignKey(User, null=False)
    name = models.CharField(max_length=128)
    surface = models.FloatField()
    percentage = models.FloatField()
    threshold = models.FloatField()
    previous_forbidden = models.ManyToManyField("Culture", related_name='cultures_previous_forbidden')
    previous_not_reco = models.ManyToManyField("Culture", related_name='cultures_previous_not_reco')
    previous_reco = models.ManyToManyField("Culture", related_name='cultures_previous_reco')
    years_return = models.IntegerField()
    crop_duration = models.IntegerField()
    soils_forbidden = models.ManyToManyField("SoilKind", related_name='cultures_soils_forbidden')
    soils_not_reco = models.ManyToManyField("SoilKind", related_name='cultures_soils_not_reco')
    soils_reco = models.ManyToManyField("SoilKind", related_name='cultures_soils_reco')
    mandatory = models.BooleanField()
    winter = models.BooleanField()
    
    
class Rotation(models.Model):
    year = models.IntegerField()
    crop = models.ForeignKey(Crop, null=True)

class Parcel(models.Model):
    user = models.ForeignKey(User, null=False)
    name = models.CharField(max_length=128)
    surface = models.FloatField(max_length=128)
    soil_kind = models.ForeignKey(SoilKind)
    position = models.ForeignKey(SoilPosition)
    history = models.ManyToManyField(Rotation)