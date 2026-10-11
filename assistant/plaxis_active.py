"""Parse phase-labelled tabulate evidence without coercing missing values."""
import re


def tabulated_active(g,obj,phase,object_name,phase_name):
    """At most two phase-scoped reads; never fall back to an unscoped table."""
    errors=[]
    for arguments in ((obj,phase),(obj,phase,'Active')):
        try:
            table=g.tabulate(*arguments)
            if not isinstance(table,str):raise ValueError('tabulate chưa trả bảng văn bản')
            lines=[line.strip() for line in table.splitlines() if line.strip()]
            if len(lines)<2:raise ValueError('bảng thiếu header hoặc dữ liệu')
            split=lambda line:line.split('\t') if '\t' in line else re.split(r'\s{2,}',line)
            header=[cell.strip() for cell in split(lines[0])]
            # The phase is explicitly passed to every call. A native scoped table
            # may label its column simply Active; never use a different phase's column.
            columns=[i for i,column in enumerate(header) if column in (
                f'Active[{phase_name}]',f'Active.{phase_name}',f'Active ({phase_name})',
                f'Active({phase_name})')]
            if not columns and 'Active' in header and not any(
                    re.match(r'Active[\[.( ]',column) for column in header):
                columns=[i for i,column in enumerate(header) if column=='Active']
            if len(columns)!=1:raise ValueError('không có đúng một cột Active mang tên phase '+phase_name)
            rows=[split(line) for line in lines[1:]]
            matching=[row for row in rows if row and row[0].strip()==object_name]
            if len(matching)!=1:raise ValueError('không có đúng một dòng đối tượng '+object_name)
            row=matching[0];index=columns[0]
            if index>=len(row):raise ValueError('dòng dữ liệu thiếu cột Active')
            raw=row[index].strip()
            if raw not in ('True','False','true','false'):raise ValueError('Active không phải boolean tường minh: '+raw[:80])
            return raw.casefold()=='true'
        except Exception as error:
            form='tabulate(obj, phase)' if len(arguments)==2 else 'tabulate(obj, phase, "Active")'
            errors.append(form+': '+str(error)[:150])
    raise ValueError('tabulate chưa xác minh đúng đối tượng/phase: '+'; '.join(errors)+
                     '. Cần lấy chữ ký tabulate thực tế bằng commands/info trên đối tượng và cung cấp bảng thô; không bỏ verify_stage.')
