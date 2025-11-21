from mongoengine import *
from ...core.mixins import AuditMixin

class Category(Document, AuditMixin):
    name = StringField(required=True, unique=True, max_length=120)
    slug = StringField(required=True, unique=True, max_length=150)
    icon = StringField()
    hot  = BooleanField(default=False)
    description = StringField()

    meta = {
        "collection": "category",
        "indexes": [
            "slug",
            {"fields": ["hot", "name"]},
            {"fields": ["name"], "unique": True}
        ]
    }

class SubCategory(Document, AuditMixin):
    name = StringField(required=True, max_length=120)
    slug = StringField(required=True, max_length=150)
    icon = StringField()
    category = ReferenceField(Category, reverse_delete_rule=CASCADE, required=True)
    description = StringField()

    meta = {
        "collection": "sub_category",
        "indexes": [
            {"fields": ["slug"], "name": "idx_subcat_slug"},
            {"fields": ["category", "name"], "unique": True}
        ]
    }

# Product

class Media(EmbeddedDocument):
    id        = StringField(required=True)
    kind      = StringField(choices=("image","video"), default="image")
    url       = StringField(required=True, max_length=500)
    alt       = StringField(max_length=200)
    is_primary= BooleanField(default=False)
    order     = IntField(default=0)

class Spec(EmbeddedDocument):
    id     = StringField(required=True)
    group  = StringField(max_length=80)
    key    = StringField(required=True, max_length=120)
    value  = StringField(required=True, max_length=500)
    order  = IntField(default=0)

class Product(Document, AuditMixin):
    name        = StringField(required=True, max_length=200)
    slug        = StringField(required=True, unique=True, max_length=220)

    price       = FloatField(required=True, min_value=0)

    category    = ReferenceField('Category', required=False, null=True)
    subcategory = ReferenceField('SubCategory', required=False, null=True)

    description = StringField()
    media       = EmbeddedDocumentListField(Media)
    specs       = EmbeddedDocumentListField(Spec)

    is_active   = BooleanField(default=True)
    is_orphan   = BooleanField(default=False)
    orphan_reason = StringField(choices=("category_deleted","subcategory_deleted","invalid_link"))
    rank_created_at = IntField()
    rank_price = IntField()


    meta = {
        "collection": "product",
        "indexes": [
            {"fields": ["slug"], "unique": True},
            {"fields": ["-created_at"]},
            {"fields": ["-price"]},
            {"fields": ["is_active","is_orphan"]},
            {"fields": ["category","subcategory"]},
            {"fields": ["name"]},
        ]
    }

class ProductKeyword(Document, AuditMixin):
    keyword = StringField(required=True, max_length=150)
    product = ReferenceField(Product, reverse_delete_rule=CASCADE, required=True)
    weight  = FloatField(default=1.0)

    meta = {
        "collection": "product_keyword",
        "indexes": [
            {"fields": ["keyword", "product"], "unique": True},
            {"fields": ["keyword", "-weight"]}
        ]
    }



