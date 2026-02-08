# Quick Start Guide

This guide will help you quickly set up a basic admin interface for your models.

## Project Structure

First, create a basic project structure:
# Quick Start Guide

This guide will help you quickly set up a basic admin interface for your models.

## Project Structure

First, create a basic project structure:

```
python
my_project/
├── main.py # Main application file
├── models.py # Database models
└── admin.py # Admin model configurations
```
## Define Models

Create your models in `models.py`:

```
from tortoise import fields, models

class Product(models.Model):
    name = fields.CharField(max_length=100)
    price = fields.DecimalField(max_digits=10, decimal_places=2)
    stock = fields.IntField(default=0)
    status = fields.BooleanField(default=True)
    image = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "products"
```

## Create Admin Configuration

Create `admin.py` to customize your model's admin interface:

```
from robyn_admin.core.admin import ModelAdmin
from robyn_admin.core.fields import DisplayType, FieldType, TableMapping

class ProductAdmin(ModelAdmin):
    
    # Display configuration
    list_display = ['name', 'price', 'stock', 'status', 'image']
    list_display_links = ['name']
    search_fields = ['name']
    list_filter = ['status']
    list_editable = ['price', 'stock']

    # Field customization
    field_labels = {
        'name': 'Product Name',
        'price': 'Price (USD)',
        'stock': 'Stock',
        'status': 'Status',
        'image': 'Product Image'
    }
    field_types = {
    'status': DisplayType.STATUS,
    'image': DisplayType.IMAGE,
    'created_at': DisplayType.DATETIME
    }

    # Status display configuration
    status_choices = {
        'status': {
        True: '<span class="badge bg-success">Active</span>',
        False: '<span class="badge bg-danger">Inactive</span>'
        }
    }

    # Image display settings
    image_width = 80
    image_height = 80
    def init(self, model):
        super().init(model)
        # Configure image display
        self.options.set_table_mapping(
            'image',
            TableMapping(
            field_type=FieldType.IMAGE,
            formatter=lambda url: f'<img src="{url}" width="{self.image_width}" height="{self.image_height}" style="object-fit: cover; border-radius: 4px;">' if url else ''
            )
        )
```

## Setup Main Application

Configure your main application in `main.py`:

```
from robyn import Robyn
from robyn_admin.core.admin import AdminSite
from models import Product
from admin import ProductAdmin

# Initialize Robyn app

app = Robyn(file)

# Database configuration
DB_CONFIG = {
    "connections": {
            "default": {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": "app.db"}
            }
    },
    "apps": {
    "models": {
    "models": ["models", "robyn_admin.models"],
    "default_connection": "default",
        }
    }
}

# Initialize admin site

admin_site = AdminSite(
    app,
    db_url="sqlite://app.db",
    modules={
    "models": ["models", "robyn_admin.models"]
    },
    generate_schemas=True
)

# Register your models
admin_site.register_model(Product, ProductAdmin)

if __name__ == "__main__":
    app.start(port=8000)

```




2. Access the admin interface:
   - Open your browser and visit: http://localhost:8000/admin
   - Login with default credentials:
     - Username: admin
     - Password: admin

## Next Steps

After getting the basic setup working, you can:

1. Add more models and customize their admin interfaces
2. Configure field display types and formats
3. Add custom actions and views
4. Customize templates and styling
5. Add user authentication and permissions

For more detailed information, check out:
- [Field Types Documentation](../components/field_types.md)
- [Model Admin Configuration](../components/model_admin.md)
- [Customization Guide](../guides/customization.md)