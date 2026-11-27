from .views import (
    AddItemsToExistingLabelingView,
    AnonymousNextItemView,
    ExportImportedItemsCsvView,
    ImportItemsCsvView,
    ListItemsView,
    ItemReservationView,
    NextItemView,
)
from django.urls import path

urlpatterns = [
    path('labelings/<int:labeling_id>/import-items-csv/', ImportItemsCsvView.as_view(),name="import-items-csv"),
    path('labelings/<int:labeling_id>/add-items-csv/', AddItemsToExistingLabelingView.as_view(),name="add-items-csv"),
    path('labelings/<int:labeling_id>/imported-items-csv/', ExportImportedItemsCsvView.as_view(),name="export-imported-items-csv"),
    path('labelings/<int:labeling_id>/items/', ListItemsView.as_view(),name='list-items'),
    path('items/<int:labeling_id>/', NextItemView.as_view(),name='next-item'),
    path('items/<int:labeling_id>/reservation/', ItemReservationView.as_view(),name='item-reservation'),
    path('items/anonymous/<uuid:token>/', AnonymousNextItemView.as_view(),name='next-item-anonymous'),
]


