// Select all checkboxes
function toggle_all_checkboxes(source) {
    var checkboxes = document.getElementsByName('batch_processing');
    for (var i = 0, n = checkboxes.length; i < n; i++) {
        checkboxes[i].checked = source.checked;
    }
}

$(window).load(function () {
    var els = document.getElementsByClassName('context-menu');
    if (els) {
        Array.prototype.forEach.call(els, function(el) {
            el.addEventListener('contextmenu', function(event) {
                var y = mouse_y(event);
                var x = mouse_x(event);
                document.getElementById('rmenu').style.top = y + 'px';
                document.getElementById('rmenu').style.left = x + 'px';
                document.getElementById('rmenu').className = 'context_menu_show';

                event.preventDefault();
                var evt = event || window.event;
                evt.returnValue = false;
            }, false);
        });
    }
});

// hide the right-click-menu if user clicked outside its boundaries
$(document).bind('click', function (event) {
    document.getElementById('rmenu').className = 'context_menu_hide';
});

function mouse_x(event) {
    if (event.pageX) {
        return event.pageX;
    } else if (event.clientX) {
        return event.clientX +
            (document.documentElement.scrollLeft ? document.documentElement.scrollLeft : document.body.scrollLeft);
    } else {
        return null;
    }
}

function mouse_y(event) {
    if (event.pageY) {
        return event.pageY;
    } else if (event.clientY) {
        return event.clientY +
            (document.documentElement.scrollTop ? document.documentElement.scrollTop : document.body.scrollTop);
    } else {
        return null;
    }
}

// Get all checked rows
function get_checked_boxes(checkbox_name) {
    var checkboxes = document.getElementsByName(checkbox_name);
    var selected_checkboxes = [];

    for (var i = 0; i < checkboxes.length; i++) {
        if (checkboxes[i].checked) {
            selected_checkboxes.push(checkboxes[i]);
        }
    }
    // Return the array if it is non-empty, or null
    return selected_checkboxes.length > 0 ? selected_checkboxes : null;
}

function process_batch(action, is_freerun) {
    var selected = get_checked_boxes('batch_processing');
    var msg = 'You are about to ' + action + ' all selected';
    var i;
    var process_name;
    var unit_name;
    var timeperiod;
    var json;

    if (confirm(msg)) {
        if (action.indexOf('skip') > -1 || action.indexOf('reprocess') > -1) {
            for (i = 0; i < selected.length; i++) {
                json = eval("(" + selected[i].value + ")");
                process_name = json['process_name'];
                timeperiod = json['timeperiod'];
                process_timeperiod(action, process_name, timeperiod, false);
                selected[i].checked = false;
            }
        } else if (action.indexOf('activate') > -1 || action.indexOf('deactivate') > -1) {
            if (is_freerun) {
                for (i = 0; i < selected.length; i++) {
                    json = eval("(" + selected[i].value + ")");
                    process_name = json['process_name'];
                    unit_name = json['unit_name'];
                    process_trigger(action, process_name, null, unit_name, is_freerun, i < selected.length -1, false);
                    selected[i].checked = false;
                }
            } else {
                for (i = 0; i < selected.length; i++) {
                    json = eval("(" + selected[i].value + ")");
                    process_name = json['process_name'];
                    timeperiod = json['timeperiod'];
                    process_trigger(action, process_name, timeperiod, null, is_freerun, i < selected.length -1, false);
                    selected[i].checked = false;
                }
            }
        } else {
            alert('Action ' + action + ' is not yet supported by Synergy Scheduler MX JavaScript library.')
        }
    }
}

function process_timeperiod(action, process_name, timeperiod, show_confirmation_dialog) {
    if (show_confirmation_dialog) {
        var msg = 'You are about to ' + action + ' ' + timeperiod + ' for ' + process_name;
        if (confirm(msg)) {
            // fall thru
        } else {
            return;
        }
    }

    var params = { 'process_name': process_name, 'timeperiod': timeperiod };
    $.get('/' + action, params, function (response) {
//        alert("response is " + response);
    });
}

function process_trigger(action, process_name, timeperiod, unit_name, is_freerun, is_batch, show_confirmation_dialog) {
    if (show_confirmation_dialog) {
        var msg = 'You are about to ' + action + ' ' + timeperiod + ' for ' + process_name;
        if (confirm(msg)) {
            // fall thru
        } else {
            return;
        }
    }

    var params;
    if (is_freerun) {
        params = { 'process_name': process_name, 'timeperiod': timeperiod, 'unit_name': unit_name, 'is_freerun': is_freerun, 'is_batch': is_batch };
    } else {
        params = { 'process_name': process_name, 'timeperiod': timeperiod, 'is_freerun': is_freerun, 'is_batch': is_batch };
    }

    $.get('/' + action, params, function (response) {
//        alert("response is " + response);
    });
}
