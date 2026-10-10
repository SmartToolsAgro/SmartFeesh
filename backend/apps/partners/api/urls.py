from django.urls import path

from . import views

urlpatterns = [
    path("suppliers", views.SupplierListView.as_view(), name="supplier-list"),
    path("suppliers/<int:supplier_id>", views.SupplierDetailView.as_view(), name="supplier-detail"),
    path("suppliers/<int:supplier_id>/archive", views.SupplierArchiveView.as_view(), name="supplier-archive"),
    path("suppliers/<int:supplier_id>/restore", views.SupplierRestoreView.as_view(), name="supplier-restore"),
]
