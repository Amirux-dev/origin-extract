"""Données synthétiques pour la CI ; aucun fichier scientifique privé n'est nécessaire."""
import csv
import io
import math
from origin_extract.core import Project, Sheet, digest


def sample_project():
    sizes = [2000] * 12 + [122] + [2000] * 5 + [3759]
    sheets = []
    reconstructed = {12, 13, 14, 16, 17, 18}
    for index, size in enumerate(sizes):
        temperature = index >= 12
        count = 7 if index in (12, 13, 14) else 10 if index == 15 else 8
        names = (['Tsample', 'Tvit', 'X', 'Y', 'R', 'phi', 'B', 'time'] if temperature else
                 ['B', 'Tsample', 'Tvit', 'X', 'Y', 'R', 'phi', 'time'])[:count]
        if count == 10:
            names = ['Tsample', 'Tvit', 'X', 'Y', 'R', 'phi', 'B', 'data', 'time', 'J']
        metadata = [dict(column=chr(65 + c), name='' if index in reconstructed else name,
                         unit='', comment='Fixture synthétique', exported_header=name,
                         reconstructed_name=name if index in reconstructed else '',
                         source='Reconstitué par cohérence, confirmé par utilisateur' if index in reconstructed else 'Origin Long Name')
                    for c, name in enumerate(names)]
        rows = []
        for row in range(size):
            values = dict(B=str(row / 1000), Tsample=str(1.5 + row / 10000), Tvit='1.7',
                          X='0.00034', Y='-0.00003', R=str(math.hypot(.00034, -.00003)),
                          phi='-5.042451', time='10:33', data='2026-01-01', J='0')
            rows.append([values[name] for name in names])
        output = io.StringIO(newline='')
        csv.writer(output, delimiter='\t', lineterminator='\n').writerows([names] + rows)
        content = output.getvalue().encode('utf-8')
        name = f'sr3ru2o7sust{index - 11}' if temperature else f'synthetique_{index + 1}'
        record = dict(book=name, sheet=name, title=name, folder='Synthétique',
                      rows=size, columns=count, file=f'{index}.txt', sha256=digest(content),
                      column_metadata=metadata)
        sheets.append(Sheet(record, content, names, rows))
    return Project('Test synthétique', 'fixture', sheets)
