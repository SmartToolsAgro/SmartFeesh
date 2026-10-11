from django.urls import path

from . import views

urlpatterns = [
    # P5-T01 · expenses
    path("expense-categories", views.ExpenseCategoryListView.as_view(), name="expense-category-list"),
    path(
        "expense-categories/<int:category_id>",
        views.ExpenseCategoryDetailView.as_view(),
        name="expense-category-detail",
    ),
    path("expenses", views.ExpenseListView.as_view(), name="expense-list"),
    path("expenses/totals", views.ExpenseTotalsView.as_view(), name="expense-totals"),
    path("expenses/<int:expense_id>", views.ExpenseDetailView.as_view(), name="expense-detail"),
    path("expenses/<int:expense_id>/approve", views.ExpenseApproveView.as_view(), name="expense-approve"),
    path("expenses/<int:expense_id>/reject", views.ExpenseRejectView.as_view(), name="expense-reject"),
    path("expenses/<int:expense_id>/receipt", views.ExpenseReceiptView.as_view(), name="expense-receipt"),
    path("lot-costs", views.LotCostsView.as_view(), name="lot-costs"),
    # P5-T03 · day labour
    path("day-labourers", views.DayLabourerListView.as_view(), name="day-labourer-list"),
    path("day-labourers/<int:labourer_id>", views.DayLabourerDetailView.as_view(), name="day-labourer-detail"),
    path("day-labour", views.DayLabourListView.as_view(), name="day-labour-list"),
    path("day-labour/<int:entry_id>", views.DayLabourDetailView.as_view(), name="day-labour-detail"),
]
