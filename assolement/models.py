from django.db import models

class TypeSol(models.Model):
    numero = models.IntegerField()
    nom = models.CharField(max_length=128)
    
class LocalisationSol(models.Model):
    code = models.CharField(max_length=1)
    nom = models.CharField(max_length=128)

class Culture(models.Model):
    nom = models.CharField(max_length=128)
    surface = models.FloatField()
    pourcentage = models.FloatField()
    tolerance = models.FloatField()
    precedents_interdits = models.ManyToManyField("Culture", related_name='cultures_interdits')
    precedents_deconseilles = models.ManyToManyField("Culture", related_name='cultures_deconseilles')
    precedents_conseilles = models.ManyToManyField("Culture", related_name='cultures_conseilles')
    annees_retour = models.IntegerField()
    duree_culture = models.IntegerField()
    sols_interdits = models.ManyToManyField("TypeSol", related_name='sols_interdits')
    sols_deconseilles = models.ManyToManyField("TypeSol", related_name='sols_deconseilles')
    sols_conseilles = models.ManyToManyField("TypeSol", related_name='sols_conseilles')
    obligatoire = models.BooleanField()
    
class Annee(models.Model):
    annee = models.IntegerField()
    culture = models.ForeignKey(Culture, null=True)

class Parcelle(models.Model):
    nom = models.CharField(max_length=128)
    surface = models.FloatField(max_length=128)
    type_de_sol = models.ForeignKey(TypeSol)
    localisation = models.ForeignKey(LocalisationSol)
    historique = models.ManyToManyField(Annee)