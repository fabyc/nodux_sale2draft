#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import groupby, chain
from functools import partial
from sql import Table
from sql.functions import Overlay, Position
from sql.operators import Concat

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond import backend
from trytond.pyson import If, Eval, Bool, PYSONEncoder, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Sale','DraftSaleStart', 'DraftSale']
__metaclass__ = PoolMeta

_ZERO = Decimal(0)

class Sale():
    __name__ = 'sale.sale'
    invoice_number_deleted = fields.Char('Invoice number deleted')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

    @classmethod
    def workflow_to_end(cls, sales):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Date = pool.get('ir.date')
        for sale in sales:
            if sale.state == 'draft':
                cls.quote([sale])
            if sale.state == 'quotation':
                cls.confirm([sale])
            if sale.state == 'confirmed':
                cls.process([sale])
            if not sale.invoices and sale.invoice_method == 'order':
                cls.raise_user_error('not_customer_invoice')
            print "Aqui genera la factura nodux_sale3 "
            grouping = getattr(sale.party, 'sale_invoice_grouping_method',
                False)
            if sale.invoices and not grouping:
                for invoice in sale.invoices:
                    if invoice.state == 'draft':
                        if not getattr(invoice, 'invoice_date', False):
                            invoice.invoice_date = Date.today()
                        if not getattr(invoice, 'accounting_date', False):
                            invoice.accounting_date = Date.today()
                        invoice.description = sale.reference
                        invoice.save()
                    invoice.number = sale.invoice_number_deleted
                    invoice.save()
                Invoice.post(sale.invoices)
                for payment in sale.payments:
                    invoice = sale.invoices[0]
                    payment.invoice = invoice.id
                    # Because of account_invoice_party_without_vat module
                    # could be installed, invoice party may be different of
                    # payment party if payment party has not any vat
                    # and both parties must be the same
                    if payment.party != invoice.party:
                        payment.party = invoice.party
                    payment.save()
            if sale.is_done():
                cls.do([sale])

class DraftSaleStart(ModelView):
    'Draft Sale'
    __name__ = 'sale.draft_sale.start'


class DraftSale(Wizard):
    'Draft Sale'
    __name__ = 'sale.draft_sale'
    start = StateView('sale.draft_sale.start',
        'nodux_sale2draft.draft_sale_start_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Draft', 'draft_', 'tryton-ok', default=True),
            ])
    draft_ = StateAction('sale.act_sale_form')

    def do_draft_(self, action):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')
        sales = Sale.browse(Transaction().context['active_ids'])
        for s in sales:
            sale = s
            invoices= Invoice.search([('description', '=', sale.reference)])
            sale.state = 'draft'
            cursor = Transaction().cursor
            for i in invoices:
                if i.estado_sri == 'AUTORIZADO':
                    self.raise_user_error('No puede reversar una factura que se encuentra autorizada por el SRI')
                else:
                    cursor.execute('DELETE FROM account_move_line WHERE move = %s' %i.move.id)
                    cursor.execute('DELETE FROM account_move WHERE id = %s' %i.move.id)
                    for line in i.lines:
                        cursor.execute('DELETE FROM account_invoice_line WHERE id = %s' %line.id)
                    cursor.execute('DELETE FROM account_invoice WHERE id = %s' %i.id)
                    sale.invoice_number_deleted = i.number
                    for payment in sale.payments:
                        cursor.execute('DELETE FROM account_statement_line WHERE id = %s' %payment.id)
                    for move in sale.moves:
                        cursor.execute('DELETE FROM stock_move WHERE id = %s' % move.id)
                    sale.invoice_state = 'none'
                    sale.shipment_state = 'none'
                    sale.description = None
                    sale.reference = None
                    sale.save()
