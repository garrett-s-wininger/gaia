from django.urls import include, path

urlpatterns = [path("todo/", include("todo.urls", namespace="todo"))]

