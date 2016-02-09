from django.conf.urls import patterns, include, url
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'assolement.views.index', name='index'),
    url(r'^index.html$', 'assolement.views.index', name='index'),
    url(r'^create_update.html$', 'assolement.views.create_update', name='create_update'),
    url(r'^remove.html$', 'assolement.views.remove', name='remove'),
    
    url(r'^update_history.html$', 'assolement.views.update_history', name='history_save'),
    
    url(r'^compute_year.html$', 'assolement.views.compute_year', name='compute_year'),
    
    
    
    url(r'^admin/', include(admin.site.urls)),
)
