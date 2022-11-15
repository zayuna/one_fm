frappe.ui.form.on('Timesheet', {
    employee: function(frm) {
		set_approver(frm)
	},
})

function set_approver(frm){
    if(frm.doc.employee){
        frappe.call({
            method: 'one_fm.one_fm.timesheet_custom.fetch_approver',
            args:{
                'employee':frm.doc.employee
            },
            callback: function(r) {
                if(r.message){
                    frm.set_value("approver",r.message)
                }
            }
        });
    }
}