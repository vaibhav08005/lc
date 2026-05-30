from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .natwest_common import result


def bank_statements(case: MortgageCase):
    return result("natwest.documentation.bank_statements", "documentation", RuleStatus.REFER, "Bank statement acceptability must be checked against NatWest packaging requirements.", section="Bank statements", criteria_type="evidence_rule", implemented_by="natwest.documentation")


def certification(case: MortgageCase):
    return result("natwest.documentation.certification", "documentation", RuleStatus.REFER, "Certification of documents and acceptable upload formats require NatWest packaging review.", section="Certification of documents", criteria_type="evidence_rule", implemented_by="natwest.documentation")


def proof_of_address_id(case: MortgageCase):
    return result("natwest.documentation.id_address", "documentation", RuleStatus.REFER, "Proof of address and ID packaging must be checked before submission.", section="Proof of address and ID Packaging", criteria_type="evidence_rule", implemented_by="natwest.documentation")


def offer_validity(case: MortgageCase):
    return result("natwest.documentation.offer_validity", "documentation", RuleStatus.REFER, "Offer validity depends on application and product stage and must be tracked outside the input YAML.", section="Offer of loan (validity)", criteria_type="manual_rule", implemented_by="natwest.documentation")
