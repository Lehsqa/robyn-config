# ModelAdmin Class

The `ModelAdmin` class is the core component for customizing how your models are displayed and managed in the admin interface.

## Basic Configuration

```python
from robyn_admin.core.admin import ModelAdmin
from robyn_admin.core.fields import DisplayType

class ProductAdmin(ModelAdmin):
    list_display = ['name', 'price', 'status']
    list_display_links = ['name']
    search_fields = ['name']
    list_filter = ['status']
```

## Available Options

### Display Configuration
- `list_display`: List of fields to display in the table view
- `list_display_links`: Fields that will be linked to the edit view
- `list_filter`: Fields that can be filtered
- `search_fields`: Fields that can be searched
- `ordering`: Default ordering fields (prefix with '-' for descending)
- `readonly_fields`: Fields that cannot be edited
- `list_editable`: Fields that can be edited directly in the list view
- `per_page`: Number of items to display per page (default: 10)

### Field Customization
- `field_labels`: Custom labels for fields
```python
field_labels = {
    'name': 'Product Name',
    'price': 'Price (USD)',
    'created_at': 'Creation Date'
}
```

- `field_types`: Display type for fields
```python
field_types = {
    'status': DisplayType.STATUS,
    'image': DisplayType.IMAGE,
    'created_at': DisplayType.DATETIME
}
```

### Display Formats
- `date_format`: Format for date fields (default: "%Y-%m-%d")
- `datetime_format`: Format for datetime fields (default: "%Y-%m-%d %H:%M:%S")
- `image_width`: Default width for image display (default: 50)
- `image_height`: Default height for image display (default: 50)

### Status Choices
Configure how status fields are displayed:
```python
status_choices = {
    'status': {
        True: '<span class="badge bg-success">Active</span>',
        False: '<span class="badge bg-danger">Inactive</span>'
    }
}
```

## Advanced Features

### Custom Display Methods
Create custom display methods for fields:
```python
def format_price(self, obj):
    return f'${obj.price:.2f}'

custom_display = {
    'price': format_price
}
```

### Table Mappings
Configure advanced table cell display:
```python
def __init__(self, model):
    super().__init__(model)
    self.options.set_table_mapping(
        'image',
        TableMapping(
            field_type=FieldType.IMAGE,
            formatter=lambda url: f'<img src="{url}" width="{self.image_width}">'
        )
    )
```

### Query Customization
Override the get_queryset method to customize the query:
```python
async def get_queryset(self, search_term: str = None, filters: Dict = None):
    queryset = await super().get_queryset(search_term, filters)
    return queryset.filter(active=True)
```

## Example Implementation

Here's a complete example showing various features:

```python
class ProductAdmin(ModelAdmin):
    # Display configuration
    list_display = ['name', 'price', 'stock', 'status', 'image']
    list_display_links = ['name']
    search_fields = ['name', 'description']
    list_filter = ['status']
    list_editable = ['price', 'stock']
    ordering = ['-created_at']
    
    # Field customization
    field_labels = {
        'name': 'Product Name',
        'price': 'Price (USD)',
        'stock': 'In Stock',
        'status': 'Status',
        'image': 'Product Image'
    }
    
    field_types = {
        'status': DisplayType.STATUS,
        'image': DisplayType.IMAGE,
        'created_at': DisplayType.DATETIME
    }
    
    # Status display
    status_choices = {
        'status': {
            True: '<span class="badge bg-success">Active</span>',
            False: '<span class="badge bg-danger">Inactive</span>'
        }
    }
    
    # Image display settings
    image_width = 80
    image_height = 80
    
    def __init__(self, model):
        super().__init__(model)
        # Configure image display
        self.options.set_table_mapping(
            'image',
            TableMapping(
                field_type=FieldType.IMAGE,
                formatter=self.format_image
            )
        )
    
    def format_image(self, url):
        if not url:
            return ''
        return f'<img src="{url}" width="{self.image_width}" height="{self.image_height}" style="object-fit: cover;">'
```

## Best Practices

1. **Field Labels**: Always provide meaningful labels for fields that users will see
2. **Search Fields**: Include fields that users are likely to search by
3. **List Display**: Show the most important fields in the list view
4. **List Editable**: Make frequently updated fields editable in the list view
5. **Status Display**: Use visual indicators (like badges) for status fields
6. **Image Display**: Set appropriate image dimensions and use object-fit for consistency 