from django.urls import re_path

from plugins.production_transporter import views

urlpatterns = [
    re_path(r'^$', views.index, name='production_transporter_manager'),
    re_path(r'articles/', views.handshake_url, name="production_transporter_handshake_url"),
    re_path(r'article/(?P<article_id>\d+)/', views.jump_url, name="production_transporter_jump_url"),
]