/* @author "Bohdan Mushkevych" */

var GRIDS = {};

var GRID_HEADER_TEMPLATE = grid_info_template(1);


/**
 * function returns a Tiles.js template for job records
 * template contains tiles_number of tiles
 * each tile has proportion 4x3 (wider than taller)
 */
function grid_info_template(tiles_number) {
    var arr = [];
    for (var i = 0; i < tiles_number; i++) {
        if (i % 2 == 0) {
            // arr.push(" A A A A ");
            // arr.push(" A A A A ");
            // arr.push(" A A A A ");
            arr.push(" A ");
        } else {
            // arr.push(" B B B B ");
            // arr.push(" B B B B ");
            // arr.push(" B B B B ");
            arr.push(" B ");
        }
    }
    return arr;
}


function get_grid(grid_name) {
    var grid;
    var el;
    if (grid_name in GRIDS) {
        grid = GRIDS[grid_name];
    } else {
        el = document.getElementById(grid_name);
        grid = new Tiles.Grid(el);
        GRIDS[grid_name] = grid;
    }
    return grid;
}


function header_tree_tile(mx_tree, tile) {
    var refresh_button = $('<button class="action_button" id="refresh_button_' + mx_tree.tree_name + '">' +
        '<i class="fa fa-refresh"></i>&nbsp;Refresh</button>').click(function (e) {
        clear_tree(mx_tree.tree_name);
        mx_trees[mx_tree.tree_name] = get_tree(mx_tree.tree_name);
        build_tree(mx_tree.tree_name);
    });

    tile.$el.append('<ul class="fa-ul">'
        + '<li title="Tree Name"><i class="fa-li fa fa-sitemap"></i>' + mx_tree.tree_name + '</li>'
        + '<li title="Dependent On"><i class="fa-li fa fa-expand"></i>' + formatJSON(mx_tree.dependent_on) + '</li>'
        + '<li title="Dependant Trees"><i class="fa-li fa fa-compress"></i>' + formatJSON(mx_tree.dependant_trees) + '</li>'
        + '</ul>');
    tile.$el.append($('<div></div>').append(refresh_button));
    tile.$el.attr('class', 'tree_header_tile');
}


function header_process_tile(process_entry, tile) {
    var flush_one_form = '<form method="GET" action="/gc/flush_one/" onsubmit="xmlhttp.send(); return false;">'
        + '<input type="hidden" name="process_name" value="' + process_entry.process_name + '" />'
        + '<input type="submit" title="flush_' + process_entry.process_name + '" class="fa-input" value="&#xf1b8"/>'
        + '</form>';

    var reprocessing_block = '<div class="table_layout">'
        + '<div class="table_layout_element">' + flush_one_form + '</div>'
        + '<div class="table_layout_element">&nbsp;</div>'
        + '<div class="table_layout_element"><textarea rows="1" cols="20" readonly>'
        + process_entry.reprocessing_queue.toString()
        + '</textarea></div>'
        + '</div>';

    var trigger_form = '<form method="GET" action="/action/trigger_now/" onsubmit="xmlhttp.send(); return false;">'
        + '<input type="hidden" name="process_name" value="' + process_entry.process_name + '" />'
        + '<input type="hidden" name="timeperiod" value="NA" />'
        + '<input type="submit" title="trigger_' + process_entry.process_name + '" class="fa-input" value="&#xf135"/>'
        + '</form>';

    var next_run_block = '<div class="table_layout">'
        + '<div class="table_layout_element">' + trigger_form + '</div>'
        + '<div class="table_layout_element">&nbsp;</div>'
        + '<div class="table_layout_element">' + process_entry.next_run_in + '</div>'
        + '</div>';

    var is_on;
    if (process_entry.is_on) {
        is_on = '<a onclick="process_trigger(\'action/deactivate_trigger\', \'' + process_entry.process_name + '\', \'NA\', null, false, true)">' +
        '<i class="fa fa-toggle-on action_toogle" title="is ON"></i></a>';
    } else {
        is_on = '<a onclick="process_trigger(\'action/activate_trigger\', \'' + process_entry.process_name + '\', \'NA\', null, false, true)">' +
        '<i class="fa fa-toggle-off action_toogle" title="is OFF"></i></a>';
    }

    var is_alive;
    if (process_entry.is_alive) {
        is_alive = '<i class="fa fa-toggle-on" title="is ON"></i>';
        tile.$el.attr('class', 'process_header_tile_on');
    } else {
        is_alive = '<i class="fa fa-toggle-off" title="is OFF"></i>';
        tile.$el.attr('class', 'process_header_tile_off');
    }

    tile.$el.append('<ul class="fa-ul">'
        + '<li title="Trigger On/Off"><i class="fa-li fa fa-power-off"></i>' + is_on + '</li>'
        + '<li title="Trigger Alive"><i class="fa-li fa fa-bolt"></i>' + is_alive + '</li>'
        + '<li title="Process Name"><i class="fa-li fa fa-terminal"></i>' + process_entry.process_name + '</li>'
        + '<li title="Next Timeperiod"><i class="fa-li fa fa-play"></i>' + process_entry.next_timeperiod + '</li>'
        // + '<li title="Next Run In"><i class="fa-li fa fa-rocket"></i>' + next_run_block + '</li>'
        // + '<li title="Reprocessing Queue"><i class="fa-li fa fa-recycle"></i>' + reprocessing_block + '</li>'
        + '</ul>'
        + next_run_block
        + reprocessing_block);
}


function info_process_tile(process_entry, tile) {
    var change_interval_form = '<form method="GET" action="/action/change_interval/" onsubmit="xmlhttp.send(); return false;">'
        + '<input type="hidden" name="process_name" value="' + process_entry.process_name + '" />'
        + '<input type="hidden" name="timeperiod" value="NA" />'
        + '<input type="text" size="8" maxlength="32" name="interval" value="' + process_entry.trigger_frequency + '" />'
        + '<input type="submit" title="Apply" class="fa-input" value="&#xf00c;"/>'
        + '</form>';

    tile.process_name = process_entry.process_name;
    tile.$el.append('<ul class="fa-ul">'
        + '<li title="Process Name"><i class="fa-li fa fa-terminal"></i>' + process_entry.process_name + '</li>'
        + '<li title="Time Qualifier"><i class="fa-li fa fa-calendar"></i>' + process_entry.time_qualifier + '</li>'
        + '<li title="Time Grouping"><i class="fa-li fa fa-cubes"></i>' + process_entry.time_grouping + '</li>'
        + '<li title="State Machine"><i class="fa-li fa fa-puzzle-piece"></i>' + process_entry.state_machine_name + '</li>'
        + '<li title="Blocking Type"><i class="fa-li fa fa-anchor"></i>' + process_entry.blocking_type + '</li>'
        + '<li title="Trigger Frequency"><i class="fa-li fa fa-heartbeat"></i>' + change_interval_form + '</li>'
        + '</ul>');
    tile.$el.attr('class', 'process_info_tile');
}


function info_job_tile(job_entry, tile, is_next_timeperiod, is_selected_timeperiod) {
    var checkbox_value = "{ process_name: '" + job_entry.process_name + "', timeperiod: '" + job_entry.timeperiod + "' }";
    var checkbox_div = '<input type="checkbox" name="batch_processing" value="' + checkbox_value + '"/>';

    var uow_button = $('<button class="action_button"><i class="fa fa-file-code-o"></i>&nbsp;Uow</button>').click(function (e) {
        var params = { action: 'action/get_uow', timeperiod: job_entry.timeperiod, process_name: job_entry.process_name };
        var viewer_url = '/viewer/object/?' + $.param(params);
        window.open(viewer_url, 'Object Viewer', 'width=450,height=400,screenX=400,screenY=200,scrollbars=1');
    });
    var event_log_button = $('<button class="action_button"><i class="fa fa-th-list"></i>&nbsp;Event&nbsp;Log</button>').click(function (e) {
        var params = { action: 'action/get_event_log', timeperiod: job_entry.timeperiod, process_name: job_entry.process_name };
        var viewer_url = '/viewer/object/?' + $.param(params);
        window.open(viewer_url, 'Object Viewer', 'width=800,height=480,screenX=400,screenY=200,scrollbars=1');
    });
    var skip_button = $('<button class="action_button"><i class="fa fa-step-forward"></i>&nbsp;Skip</button>').click(function (e) {
        process_job('action/skip', tile.tree_name, tile.process_name, tile.timeperiod, null, null);
    });
    var reprocess_button = $('<button class="action_button"><i class="fa fa-repeat"></i>&nbsp;Reprocess</button>').click(function (e) {
        process_job('action/reprocess', tile.tree_name, tile.process_name, tile.timeperiod, null, null);
    });
    var uow_log_button = $('<button class="action_button"><i class="fa fa-file-text-o"></i>&nbsp;Uow&nbsp;Log</button>').click(function (e) {
        var params = { action: 'action/get_uow_log', timeperiod: job_entry.timeperiod, process_name: job_entry.process_name };
        var viewer_url = '/viewer/object/?' + $.param(params);
        window.open(viewer_url, 'Object Viewer', 'width=800,height=480,screenX=400,screenY=200,scrollbars=1');
    });
    var flow_button = $('<button class="action_button"><i class="fa fa-random"></i>Workflow</button>').click(function (e) {
        var params = { action: 'flow/details/flow', timeperiod: job_entry.timeperiod, process_name: job_entry.process_name };
        var viewer_url = '/viewer/flow/?' + $.param(params);
        window.open(viewer_url, 'Flow Viewer', 'width=800,height=480,screenX=400,screenY=200,scrollbars=1');
    });

    tile.process_name = job_entry.process_name;
    tile.timeperiod = job_entry.timeperiod;
    tile.$el.click(function (e) {
        tile_selected(tile);
    });

    if (is_next_timeperiod) {
        tile.$el.attr('class', job_entry.state + ' is_next_timeperiod');
    } else {
        tile.$el.attr('class', job_entry.state);
    }

    if (is_selected_timeperiod) {
        tile.$el.attr('class', job_entry.state + ' is_selected_timeperiod');
    }

    tile.$el.append($('<div class="tile_component"></div>').append(checkbox_div));
    tile.$el.append($('<div class="tile_component"></div>').append('<ul class="fa-ul">'
        + '<li title="Timeperiod"><i class="fa-li fa fa-clock-o"></i>' + job_entry.timeperiod + '</li>'
        + '<li title="State"><i class="fa-li fa fa-flag-o"></i>' + job_entry.state + '</li>'
        + '<li title="# of fails"><i class="fa-li fa fa-exclamation-triangle"></i>' + job_entry.number_of_failures + '</li>'
        + '</ul>'));
    tile.$el.append('<div class="clear"></div>');
    tile.$el.append($('<div></div>').append(uow_button).append(skip_button));
    tile.$el.append($('<div></div>').append(uow_log_button).append(reprocess_button));
    tile.$el.append($('<div></div>').append(event_log_button).append(flow_button));
}


function build_header_grid(grid_name, grid_template, builder_function, info_obj) {
    var grid = get_grid(grid_name);

    // by default, each tile is an empty div, we'll override creation
    // to add a tile number to each div
    grid.createTile = function (tileId) {
        var tile = new Tiles.Tile(tileId);
        builder_function(info_obj, tile);
        return tile;
    };

    // common post-build function calls per grid
    grid_post_constructor(grid, grid_template);
}


function build_process_grid(grid_name, tree_obj) {
    var grid = get_grid(grid_name);

    // by default, each tile is an empty div, we'll override creation
    // to add a tile number to each div
    grid.createTile = function (tileId) {
        var tile = new Tiles.Tile(tileId);

        // retrieve process entry
        var process_name = tree_obj.sorted_process_names[tileId - 1];  // tileId starts with 1
        var info_obj = tree_obj.processes[process_name];

        info_process_tile(info_obj, tile);
        return tile;
    };

    // common post-build function calls per grid
    var template = grid_info_template(tree_obj.sorted_process_names.length);
    grid_post_constructor(grid, template);
}


function build_job_grid(grid_name, tree_level, next_timeperiod, selected_timeperiod, tree_obj) {
    var grid = get_grid(grid_name);
    var timeperiods = keys_to_list(tree_level.children, true);

    // set the tree for a grid
    grid.tree_obj = tree_obj;

    // by default, each tile is an empty div, we'll override creation
    // to add a tile number to each div
    grid.createTile = function (tileId) {
        var tile = new Tiles.Tile(tileId);
        tile.grid = grid;
        tile.tree_name = tree_obj.tree_name;

        // translate sequential IDs to the Timeperiods
        var reverse_index = timeperiods.length - tileId;    // tileId starts with 1
        var timeperiod = timeperiods[reverse_index];

        // retrieve job_record
        var info_obj = tree_level.children[timeperiod];

        info_job_tile(info_obj, tile, next_timeperiod==timeperiod, selected_timeperiod==timeperiod);
        return tile;
    };

    // common post-build function calls per grid
    var template = grid_info_template(timeperiods.length);
    grid_post_constructor(grid, template);
}


function grid_post_constructor(grid, template) {
    grid.template = Tiles.Template.fromJSON(template);

    // return the number of columns from original template
    // so that template does not change on the window resize
    grid.resizeColumns = function () {
        return this.template.numCols;
    };

    // adjust number of tiles to match selected template
    var ids = range(1, grid.template.rects.length);
    grid.updateTiles(ids);
    grid.resize();
    grid.redraw(true);

    // wait until users finishes resizing the browser
    var debounced_resize = debounce(function () {
        grid.resize();
        grid.redraw(true);
    }, 200);

    // when the window resizes, redraw the grid
    $(window).resize(debounced_resize);
}


function get_tree_nodes(process_name, timeperiod){
    var response_text = $.ajax({
        data: {'process_name': process_name, 'timeperiod': timeperiod},
        dataType: "json",
        type: "GET",
        url: '/details/tree_nodes/',
        cache: false,
        async: false
    }).responseText;
    return JSON.parse(response_text);
}


function get_tree(tree_name){
    var response_text = $.ajax({
        data: {'tree_name': tree_name},
        dataType: "json",
        type: "GET",
        url: '/details/tree/',
        cache: false,
        async: false
    }).responseText;
    return JSON.parse(response_text);
}


function tile_selected(tile) {
    // step 1: check if the tile is already selected
    if (tile.$el.attr('class').indexOf('is_selected_timeperiod') > -1) {
        // this tile is already selected
        // yet, we let it proceed as this is analogue to the "refresh"
        // return;
    }

    // step 2: remove is_selected_timeperiod class from all tiles in the given grid
    var i;
    var tile_number = tile.grid.tiles.length;
    for (i = 0; i < tile_number; i++) {
        var i_tile = tile.grid.tiles[i];
        var new_class = i_tile.$el.attr('class').replace(' is_selected_timeperiod', '');
        i_tile.$el.attr('class', new_class);
    }

    // step 3: assign is_selected_timeperiod to the given title
    tile.$el.attr('class', tile.$el.attr('class') + ' is_selected_timeperiod');

    // step 4: iterate over grids and rebuild them
    var tree_obj = tile.grid.tree_obj;
    var process_number = tree_obj.sorted_process_names.length;
    if (tile.process_name == tree_obj.sorted_process_names[process_number - 1]) {
        // this is bottom-level process. no grid rebuilding is possible
        return;
    }

    var higher_next_timeperiod = tile.timeperiod;
    var higher_process_name = tile.process_name;
    var is_beyond_cut_off = false;
    var selected_timeperiod = undefined;

    for (i = 0; i < process_number; i++) {
        var i_process_name = tree_obj.sorted_process_names[i];
        if (is_beyond_cut_off == false) {
            if (i_process_name == tile.process_name) {
                is_beyond_cut_off = true;
                continue;
            } else {
                continue;
            }
        }

        // fetch child nodes for higher_process_name
        var tree_level = get_tree_nodes(higher_process_name, higher_next_timeperiod);
        var process_obj = tree_obj.processes[i_process_name];

        higher_process_name = i_process_name;
        if (process_obj.next_timeperiod in tree_level.children) {
            higher_next_timeperiod = process_obj.next_timeperiod;
        } else {
            selected_timeperiod = Math.max.apply(Math, keys_to_list(tree_level.children, true));
            higher_next_timeperiod = selected_timeperiod;
        }

        // refresh job tiles: empty the grid-info
        var grid_name = 'grid-info-' + i_process_name;
        clear_grid(grid_name);

        // refresh job tiles: reconstruct the grid-info
        build_job_grid(grid_name, tree_level, process_obj.next_timeperiod, selected_timeperiod, tree_obj);

        // refresh process tiles: empty the grid-header
        grid_name = 'grid-header-' + i_process_name;
        clear_grid(grid_name);

        // refresh process tiles: reconstruct the grid-header
        process_obj = get_tree(tree_obj.tree_name).processes[i_process_name];
        build_header_grid(grid_name, GRID_HEADER_TEMPLATE, header_process_tile, process_obj);
    }
}


function clear_grid(grid_name) {
    var grid = get_grid(grid_name);
    grid.removeTiles(range(1, grid.tiles.length));
}


function clear_tree(tree_name) {
    var tree_obj = mx_trees[tree_name];
    var process_number = tree_obj.sorted_process_names.length;
    var process_name = null;

    for (var i = 0; i < process_number; i++) {
        process_name = tree_obj.sorted_process_names[i];
        clear_grid("grid-header-" + process_name);
        clear_grid("grid-info-" + process_name);
    }
}


function build_tree(tree_name) {
    var i;
    var process_obj = null;
    var process_name = null;
    var tree_level = null;

    var tree_obj = mx_trees[tree_name];
    var process_number = tree_obj.sorted_process_names.length;

    // *** HEADER ***
    build_header_grid("grid-header-" + tree_obj.tree_name, GRID_HEADER_TEMPLATE, header_tree_tile, tree_obj);

    for (i = 0; i < process_number; i++) {
        process_name = tree_obj.sorted_process_names[i];
        process_obj = tree_obj.processes[process_name];
        build_header_grid("grid-header-" + process_name, GRID_HEADER_TEMPLATE, header_process_tile, process_obj);
    }

    // *** INFO ***
    build_process_grid("grid-info-" + tree_obj.tree_name, tree_obj);

    var higher_next_timeperiod = null;
    var higher_process_name = null;
    for (i = 0; i < process_number; i++) {
        process_name = tree_obj.sorted_process_names[i];

        if (i == 0) {
            // fetching top level of the tree
            tree_level = get_tree_nodes(process_name, higher_next_timeperiod);
        } else {
            tree_level = get_tree_nodes(higher_process_name, higher_next_timeperiod);
        }

        process_obj = tree_obj.processes[process_name];
        higher_process_name = process_name;
        higher_next_timeperiod = process_obj.next_timeperiod;

        build_job_grid("grid-info-" + process_name, tree_level, process_obj.next_timeperiod, undefined, tree_obj);
    }
}


/**
 * main method for the MX PAGE script
 * iterates over the @mx_trees map and commands building of the MX trees
 * NOTICE: variable @mx_trees is in the format {tree_name: tree_obj}
 *         and is set in mx_page_tiles.html by the templating engine
 */
$(document).ready(function () {
    for (var tree_name in mx_trees) {
        if (!mx_trees.hasOwnProperty(tree_name)) {
            continue;
        }

        build_tree(tree_name);
    }
});
