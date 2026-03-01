from django.shortcuts import render

def index(request):
    return render(request, "ticket_dashboard/index.html")


""" 
from django.shortcuts import render
import logging

logger = logging.getLogger(__name__)

MODEL_REGISTRY = {
    "Invoice Finance": (ApplicationData, 'review_applications_with_scores'),
    "Trade Finance": (tf_ApplicationData, 'review_tf_applications_with_scores'),
    "SCF": (scf_ApplicationData, 'review_scf_applications_with_scores'),
    "IPF": (IPF_ApplicationData, 'review_ipf_applications_with_scores'),
}


def ticket_dashboard(request):
    context = base_context(request)
    selected_originator = context.get('selected_originator')

    transaction_id = request.GET.get('transaction_id') or None
    abn = request.GET.get('abn')
    originator_name_from_url = request.GET.get('originator')
    product = request.GET.get('product')

    context.update({
        'abn': abn,
        'product': product,
    })

    model_entry = MODEL_REGISTRY.get(product)
    if not model_entry:
        logger.warning(f"[ticket_dashboard] Unrecognized product type: {product}")
        context['application_data'] = None
        context['raw_application'] = None
        return render(request, 'ticket_dashboard.html', context)

    model_class, _ = model_entry

    try:
        if not transaction_id:
            logger.info("[ticket_dashboard] No valid transaction_id provided. Falling back to abn + originator lookup.")
            application = model_class.objects.filter(
                abn=abn,
                originator=originator_name_from_url
            ).order_by('-id').first()
            if application:
                transaction_id = application.transaction_id
        else:
            application = model_class.objects.get(transaction_id=transaction_id)

        if not application:
            logger.error(f"[ticket_dashboard] Application not found (abn={abn}, originator={originator_name_from_url})")
            context['application_data'] = None
            context['raw_application'] = None
            return render(request, 'ticket_dashboard.html', context)

        context['transaction_id'] = transaction_id

        enriched_data = build_application_data([application], selected_originator)
        context['application_data'] = enriched_data[0] if enriched_data else None
        context['raw_application'] = application

        # ✅ Add explicit tokens to context so the template can access them directly
        context.update({
            'bureau_token': application.bureau_token,
            'bankstatements_token': application.bankstatements_token,
            'accounting_token': application.accounting_token,
            'ppsr_token': application.ppsr_token,
        })

    except model_class.DoesNotExist:
        logger.error(f"[ticket_dashboard] {product} application with transaction_id '{transaction_id}' not found.")
        context['application_data'] = None
        context['raw_application'] = None
    except Exception as e:
        logger.exception(f"[ticket_dashboard] Unexpected error: {e}")
        context['application_data'] = None
        context['raw_application'] = None

    return render(request, 'ticket_dashboard.html', context)

    """