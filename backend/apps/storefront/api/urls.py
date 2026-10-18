from django.urls import path

from . import views

urlpatterns = [
    # The public site, no login (D-184).
    path("site/catalog", views.SiteCatalogView.as_view(), name="site-catalog"),
    path("site/products/<int:product_id>/photo", views.SiteProductPhotoView.as_view(), name="site-product-photo"),
    path("site/requests", views.SiteRequestView.as_view(), name="site-requests"),
    # The office.
    path("site-products", views.SiteProductListView.as_view(), name="site-product-list"),
    path("site-products/<int:site_product_id>", views.SiteProductDetailView.as_view(), name="site-product-detail"),
    path("web-requests", views.WebRequestListView.as_view(), name="web-request-list"),
    path("web-requests/<int:request_id>", views.WebRequestDetailView.as_view(), name="web-request-detail"),
    path("web-requests/<int:request_id>/status", views.WebRequestStatusView.as_view(), name="web-request-status"),
]
