import zlib, argparse


def parse_args():
    parser = argparse.ArgumentParser(description="scan the given ra wal file and optionally truncate the corrupted entries")
    parser.add_argument("wal_file_path", help="the wal file path")
    parser.add_argument("--truncate", action="store_true", help="truncate the wal file")
    parser.add_argument("--force", action="store_true", help="truncate the wal file even the corrupted entries are not at the tail, make sure that you know what you are doing.")
    args = parser.parse_args()
    return args.wal_file_path, args.truncate, args.force


def bin_to_int(bin):
    result = 0
    for b in bin:
        result = result*256+int(b)
    return result


def is_set(x, n):
    return x & 2 ** n != 0


def read_file_magic(f):
    magic = f.read(4)
    version = f.read(1)
    print("file magic[%s]"%str(magic))
    print("file version[%d]"%bin_to_int(version))


def read_entry(f):
    idf = f.read(3)
    if not is_set(idf[0], 6):
        parse_name_header(f)
    check_sum = f.read(4)
    if bin_to_int(check_sum) == 0:
        print("checksum is zero, meet file tail[%d], stop."%f.tell())
        return False, False
    entry_len = bin_to_int(f.read(4))
    if entry_len > 0:
        entry = f.read(entry_len+16)
        idx = entry[:8]
        term = entry[8:16]
        data = entry[16:]
        expect_check_sum = zlib.adler32(entry)
        actual_check_sum = bin_to_int(check_sum)
        if expect_check_sum != actual_check_sum:
            print("check sum failed, expect_checksum[%d] actual_checksum[%d] entry_len[%d] pos[%d]."%(expect_check_sum, actual_check_sum, entry_len, f.tell()))
            return True, True
    return True, False


def parse_name_header(f):
    name_len = bin_to_int(f.read(2))
    if name_len > 0:
        name = f.read(name_len)


def scan_wal(wal_path):
    final_truncate_from, is_tail_corrupted = -1, True
    normal_count, corrupted_count = 0, 0
    with open(wal_path, "rb") as f:
        read_file_magic(f)
        has_next = True
        while has_next:
            entry_begin = f.tell()
            has_next, corrupted = read_entry(f)
            if corrupted:
                corrupted_count += 1
                if final_truncate_from < 0:
                    final_truncate_from = entry_begin
            elif has_next:
                normal_count += 1
            if has_next and final_truncate_from > 0 and not corrupted:
                print("find normal entry after corrupted entries, entry begin at[%d]."%entry_begin)
                is_tail_corrupted = False
            if not has_next:
                break
        final_truncate_to = f.tell()
    return final_truncate_from, final_truncate_to, is_tail_corrupted, normal_count, corrupted_count


def truncate_wal(wal_path, truncate_from, truncate_to):
    paddin_len = truncate_to-truncate_from+1
    print("truncate file[%s] from[%d] to[%d] len[%d]."%(wal_path, truncate_from, truncate_to, paddin_len))
    with open(wal_path, "rb+") as f:
        padding = bytes(paddin_len)
        f.seek(truncate_from)
        origin = f.read(paddin_len)
        f.seek(truncate_from)
        f.write(padding)


if __name__ == "__main__":
    wal_file_path, truncate, force = parse_args()

    truncate_from, truncate_to, is_tail_corrupted, normal_count, corrupted_count = scan_wal(wal_file_path)
    if truncate_from < 0:
        print("wal file checksum pass, entries[%d]."%normal_count)
        exit(0)

    print("scan wal file, find %d normal entries, %d corrupted entries."%(normal_count, corrupted_count))

    if truncate and truncate_from > 0:
        if not force and not is_tail_corrupted:
            print("wal file is not tail corrupted, if still want to do truncating, please set the [force] flag.")
            exit(0)
        truncate_wal(wal_file_path, truncate_from, truncate_to)
    
