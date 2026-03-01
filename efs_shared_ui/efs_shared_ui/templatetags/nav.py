from django import template
register = template.Library()

@register.simple_tag(takes_context=True)
def is_active(context, key):
    return "active" if context.get("EFS_SERVICE_NAME") == key else ""
