from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from .models import Widget


if settings.BENCH_USE_REST:
    from rest_framework import generics, serializers
    from django_filters.rest_framework import DjangoFilterBackend

    class WidgetSerializer(serializers.ModelSerializer):
        class Meta:
            model = Widget
            fields = ['id', 'name']

    class Widgets(generics.ListAPIView):
        queryset = Widget.objects.order_by('id')
        serializer_class = WidgetSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['name']

    widgets = Widgets.as_view()
else:
    def widgets(request):
        rows = Widget.objects.filter(name=request.GET['name']).order_by('id').values('id', 'name')
        return JsonResponse(list(rows), safe=False)


urlpatterns = [path('widgets/', widgets), path('admin/', admin.site.urls)]
