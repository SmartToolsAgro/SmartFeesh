from django.urls import path

from . import views

urlpatterns = [
    path("suppliers", views.SupplierListView.as_view(), name="supplier-list"),
    path("suppliers/<int:supplier_id>", views.SupplierDetailView.as_view(), name="supplier-detail"),
    path("suppliers/<int:supplier_id>/archive", views.SupplierArchiveView.as_view(), name="supplier-archive"),
    path("suppliers/<int:supplier_id>/restore", views.SupplierRestoreView.as_view(), name="supplier-restore"),
    path("customers", views.CustomerListView.as_view(), name="customer-list"),
    path("customers/<int:customer_id>", views.CustomerDetailView.as_view(), name="customer-detail"),
    path("customers/<int:customer_id>/archive", views.CustomerArchiveView.as_view(), name="customer-archive"),
    path("customers/<int:customer_id>/restore", views.CustomerRestoreView.as_view(), name="customer-restore"),
]
