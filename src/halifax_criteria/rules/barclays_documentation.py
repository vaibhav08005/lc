from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import result


def id_address_verification(case: MortgageCase):
    return result("barclays.documentation.id_address", "documentation", RuleStatus.REFER, "ID and address verification must be checked against Barclays acceptable document criteria.", section="ID and Address verification", criteria_type="evidence_rule", implemented_by="barclays.id_address_verification")


def supporting_documentation(case: MortgageCase):
    return result("barclays.documentation.supporting", "documentation", RuleStatus.REFER, "Supporting documentation and packaging requirements must be checked before submission.", section="Supporting documentation - Residential", criteria_type="evidence_rule", implemented_by="barclays.supporting_documentation")


def internet_bank_statements(case: MortgageCase):
    return result("barclays.documentation.internet_bank_statements", "documentation", RuleStatus.REFER, "Internet bank statements must satisfy Barclays document acceptability criteria.", section="Internet bank statements - Residential", criteria_type="evidence_rule", implemented_by="barclays.internet_bank_statements")


def offer_validity(case: MortgageCase):
    return result("barclays.documentation.offer_validity", "documentation", RuleStatus.REFER, "Offer validity depends on application/product stage and must be tracked outside the case YAML.", section="Offer validity", criteria_type="manual_rule", implemented_by="barclays.offer_validity")
