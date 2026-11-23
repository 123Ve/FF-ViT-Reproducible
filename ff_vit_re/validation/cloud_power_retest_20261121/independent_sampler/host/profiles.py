"""Measurement contracts shared by the builder, collector and analyzer."""
STRICT = 'strict18'
DIAGNOSTIC = 'diagnostic17'
DIAGNOSTIC16 = 'diagnostic16'
ALL_PROFILES = (STRICT, DIAGNOSTIC, DIAGNOSTIC16)
ALL = (1 << 18) - 1
SENTINEL = -(1 << 63)


def metadata(profile):
    if profile not in ALL_PROFILES:
        raise ValueError('unknown measurement profile '+str(profile))
    excluded = [7,15] if profile == DIAGNOSTIC16 else [7] if profile == DIAGNOSTIC else []
    count = 18-len(excluded)
    return dict(measurement_profile=profile, included_mask=ALL ^ sum(1 << r for r in excluded),
                included_count=count, excluded_rails=excluded,
                scope=f'{count}-rail diagnostic' if excluded else
                      '18 monitored supply rails; not external whole-board input power')


def matches(value, profile):
    return all(type(value.get(key)) is type(expected) and value[key] == expected
               for key, expected in metadata(profile).items())


def paths(profile):
    metadata(profile)
    suffix = '_DIAG16' if profile == DIAGNOSTIC16 else '_DIAG17' if profile == DIAGNOSTIC else ''
    return 'FIRMWARE_IDENTITY'+suffix+'.json', 'SHA256SUMS'+suffix+'.json', 'SD_CARD'+suffix


def qualified(status, profile):
    expected = metadata(profile)
    ready = status.get('conversion_ready_mask')
    warnings = status.get('excluded_negative_samples')
    included = status.get('included_negative_samples')
    return (matches(status, profile) and status.get('sampler_profile_rails') == expected['included_count'] and
            status.get('configured_mask') == ALL and status.get('observed_mask') == ALL and
            type(ready) is int and 0 <= ready <= ALL and
            (profile != STRICT or ready == ALL) and
            type(warnings) is int and warnings >= 0 and type(included) is int and included >= 0 and
            (profile != STRICT or warnings == included == 0))


def raw_power_ok(row, profile, capture=False):
    flags = row['flags']
    signed = row['shunt'] >= 32768 or row['current'] >= 32768
    if (row['rail'] not in range(18) or row['config'] != 0x4527 or row['calibration'] != 2048 or
        bool(flags & 2) != bool(row['mask'] & 8) or row['mask'] & 4 or
        row['shunt'] in (32767,32768) or row['current'] in (32767,32768) or
        row['bus'] >= 32767 or row['power'] == 65535):
        return False
    if (profile != STRICT and flags in (256,258) and
        (capture or row['rail'] in metadata(profile)['excluded_rails'])):
        return signed and row['power_uW'] == SENTINEL
    return (flags in (1,3) and not signed and
            row['power_uW'] == row['power'] * (31250 if row['rail'] == 10 else 12500))


def raw_capture_ok(row, profile):
    """A negative-only diagnostic record is observable, not valid included power."""
    return raw_power_ok(row,profile,capture=True)
