function dump_dom(fig, out_path)
% DUMP_DOM Serialize key Handle Graphics DOM properties of a figure to JSON.
% Compatible with both MATLAB and NumKit.

    fid = fopen(out_path, 'w');
    if fid < 0
        error('dump_dom: cannot open %s', out_path);
    end

    fpos = safe_get(fig, 'Position', []);
    fcol = safe_get(fig, 'Color', []);
    ax_list = collect_axes(fig);

    fprintf(fid, '{\n');
    fprintf(fid, '  "position": %s,\n', fmt_num_vec(fpos));
    fprintf(fid, '  "color": %s,\n', fmt_val(fcol));
    fprintf(fid, '  "numAxes": %d,\n', numel(ax_list));
    fprintf(fid, '  "axes": [\n');

    for ai = 1:numel(ax_list)
        ax = ax_list{ai};
        cls_name = '';
        try
            cls_name = class(ax);
        catch
        end
        is_polar = ~isempty(strfind(lower(cls_name), 'polar'));

        fprintf(fid, '    {\n');
        fprintf(fid, '      "isPolar": %s,\n', fmt_bool(is_polar));
        fprintf(fid, '      "position": %s,\n', fmt_num_vec(safe_get(ax, 'Position', [])));
        fprintf(fid, '      "visible": %s,\n', fmt_str(safe_get(ax, 'Visible', '')));
        fprintf(fid, '      "box": %s,\n', fmt_str(safe_get(ax, 'Box', '')));
        fprintf(fid, '      "xGrid": %s,\n', fmt_str(safe_get(ax, 'XGrid', '')));
        fprintf(fid, '      "yGrid": %s,\n', fmt_str(safe_get(ax, 'YGrid', '')));
        fprintf(fid, '      "xMinorGrid": %s,\n', fmt_str(safe_get(ax, 'XMinorGrid', '')));
        fprintf(fid, '      "yMinorGrid": %s,\n', fmt_str(safe_get(ax, 'YMinorGrid', '')));
        fprintf(fid, '      "xLim": %s,\n', fmt_num_vec(safe_get(ax, 'XLim', [])));
        fprintf(fid, '      "yLim": %s,\n', fmt_num_vec(safe_get(ax, 'YLim', [])));
        fprintf(fid, '      "rLim": %s,\n', fmt_num_vec(safe_get(ax, 'RLim', [])));
        fprintf(fid, '      "xTick": %s,\n', fmt_num_vec(safe_get(ax, 'XTick', [])));
        fprintf(fid, '      "yTick": %s,\n', fmt_num_vec(safe_get(ax, 'YTick', [])));
        fprintf(fid, '      "xScale": %s,\n', fmt_str(safe_get(ax, 'XScale', '')));
        fprintf(fid, '      "yScale": %s,\n', fmt_str(safe_get(ax, 'YScale', '')));
        fprintf(fid, '      "xDir": %s,\n', fmt_str(safe_get(ax, 'XDir', '')));
        fprintf(fid, '      "yDir": %s,\n', fmt_str(safe_get(ax, 'YDir', '')));
        fprintf(fid, '      "dataAspectRatioMode": %s,\n', fmt_str(safe_get(ax, 'DataAspectRatioMode', '')));
        fprintf(fid, '      "title": %s,\n', fmt_val(safe_label_str(ax, 'Title')));
        fprintf(fid, '      "subtitle": %s,\n', fmt_val(safe_label_str(ax, 'Subtitle')));
        fprintf(fid, '      "xLabel": %s,\n', fmt_val(safe_label_str(ax, 'XLabel')));
        fprintf(fid, '      "yLabel": %s,\n', fmt_val(safe_label_str(ax, 'YLabel')));

        % Legend info
        lg = safe_get(ax, 'Legend', []);
        has_lg = ~isempty(lg);
        lg_str = [];
        lg_loc = '';
        lg_box = '';
        if has_lg
            lg_str = safe_get(lg, 'String', []);
            lg_loc = safe_get(lg, 'Location', '');
            lg_box = safe_get(lg, 'Box', '');
        end
        fprintf(fid, '      "hasLegend": %s,\n', fmt_bool(has_lg));
        fprintf(fid, '      "legendString": %s,\n', fmt_val(lg_str));
        fprintf(fid, '      "legendLocation": %s,\n', fmt_str(lg_loc));
        fprintf(fid, '      "legendBox": %s,\n', fmt_str(lg_box));

        % Children
        ch_arr = safe_get(ax, 'Children', []);
        nch = numel(ch_arr);
        fprintf(fid, '      "numChildren": %d,\n', nch);
        fprintf(fid, '      "children": [\n');
        for ci = 1:nch
            c = ch_arr(ci);
            fprintf(fid, '        {\n');
            fprintf(fid, '          "type": %s,\n', fmt_str(safe_get(c, 'Type', '')));
            fprintf(fid, '          "visible": %s,\n', fmt_str(safe_get(c, 'Visible', '')));
            fprintf(fid, '          "handleVisibility": %s,\n', fmt_str(safe_get(c, 'HandleVisibility', '')));
            fprintf(fid, '          "displayName": %s,\n', fmt_val(safe_get(c, 'DisplayName', '')));
            fprintf(fid, '          "lineStyle": %s,\n', fmt_str(safe_get(c, 'LineStyle', '')));
            fprintf(fid, '          "marker": %s,\n', fmt_str(safe_get(c, 'Marker', '')));
            fprintf(fid, '          "color": %s,\n', fmt_val(safe_get(c, 'Color', [])));
            fprintf(fid, '          "markerFaceColor": %s,\n', fmt_val(safe_get(c, 'MarkerFaceColor', [])));
            fprintf(fid, '          "lineWidth": %s,\n', fmt_num_scalar(safe_get(c, 'LineWidth', [])));
            fprintf(fid, '          "markerSize": %s\n', fmt_num_scalar(safe_get(c, 'MarkerSize', [])));
            if ci < nch
                fprintf(fid, '        },\n');
            else
                fprintf(fid, '        }\n');
            end
        end
        fprintf(fid, '      ]\n');
        if ai < numel(ax_list)
            fprintf(fid, '    },\n');
        else
            fprintf(fid, '    }\n');
        end
    end

    fprintf(fid, '  ]\n');
    fprintf(fid, '}\n');
    fclose(fid);
end

function ax_list = collect_axes(fig)
    ax_list = {};
    ch = safe_get(fig, 'Children', []);
    for i = 1:numel(ch)
        c = ch(i);
        t = lower(to_char(safe_get(c, 'Type', '')));
        if strcmp(t, 'axes') || strcmp(t, 'polaraxes')
            ax_list{end + 1} = c;
        elseif strcmp(t, 'tiledlayout')
            tch = safe_get(c, 'Children', []);
            for j = 1:numel(tch)
                tc = tch(j);
                tt = lower(to_char(safe_get(tc, 'Type', '')));
                if strcmp(tt, 'axes') || strcmp(tt, 'polaraxes')
                    ax_list{end + 1} = tc;
                end
            end
        end
    end
end

function v = safe_get(h, prop, defval)
    v = defval;
    try
        v = get(h, prop);
    catch
    end
end

function s = safe_label_str(ax, prop)
    s = '';
    try
        h = get(ax, prop);
        if ~isempty(h)
            s = get(h, 'String');
        end
    catch
    end
end

function s = to_char(v)
    if ischar(v)
        if size(v, 1) > 1
            parts = cell(1, size(v, 1));
            for r = 1:size(v, 1)
                parts{r} = strtrim(v(r, :));
            end
            s = strjoin(parts, '\n');
        else
            s = v;
        end
    elseif isstring(v)
        if numel(v) == 1
            s = char(v);
        else
            s = char(strjoin(v(:)', '\n'));
        end
    elseif islogical(v) && numel(v) == 1
        if v
            s = 'on';
        else
            s = 'off';
        end
    else
        % Handles MATLAB enum/OnOffSwitchState objects via char(v).
        s = '';
        try
            c = char(v);
            if ischar(c) && size(c, 1) == 1
                s = c;
            end
        catch
        end
    end
end

function s = fmt_bool(b)
    if b
        s = 'true';
    else
        s = 'false';
    end
end

function s = fmt_num_scalar(v)
    if isnumeric(v) && numel(v) == 1 && isfinite(double(v))
        s = sprintf('%.6g', double(v));
    else
        s = 'null';
    end
end

function s = fmt_num_vec(v)
    if ~isnumeric(v) || isempty(v)
        s = '[]';
        return;
    end
    dv = double(v(:));
    parts = cell(1, numel(dv));
    for i = 1:numel(dv)
        if isfinite(dv(i))
            parts{i} = sprintf('%.6g', dv(i));
        else
            parts{i} = 'null';
        end
    end
    s = ['[' strjoin(parts, ', ') ']'];
end

function s = fmt_str(v)
    c = to_char(v);
    s = ['"' escape_json(c) '"'];
end

function s = fmt_val(v)
    if isempty(v)
        s = 'null';
    elseif isnumeric(v)
        s = fmt_num_vec(v);
    elseif ischar(v)
        s = fmt_str(v);
    elseif isstring(v)
        if numel(v) == 1
            s = fmt_str(v);
        else
            parts = cell(1, numel(v));
            for i = 1:numel(v)
                parts{i} = fmt_str(v(i));
            end
            s = ['[' strjoin(parts, ', ') ']'];
        end
    elseif iscell(v)
        parts = cell(1, numel(v));
        for i = 1:numel(v)
            parts{i} = fmt_val(v{i});
        end
        s = ['[' strjoin(parts, ', ') ']'];
    else
        s = 'null';
    end
end

function out = escape_json(c)
    out = '';
    for i = 1:numel(c)
        ch = c(i);
        code = double(ch);
        if ch == '\'
            out = [out '\\'];
        elseif ch == '"'
            out = [out '\"'];
        elseif code == 10
            out = [out '\n'];
        elseif code == 13
            out = [out '\r'];
        elseif code == 9
            out = [out '\t'];
        elseif code >= 32
            out = [out ch];
        end
    end
end
