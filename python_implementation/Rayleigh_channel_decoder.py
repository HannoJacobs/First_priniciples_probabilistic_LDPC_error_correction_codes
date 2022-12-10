print("\n")
import numpy as np
import random
import heapq
import time
import os

def main():
    # base_mat_filename = "NR_1_5_44.txt"
    # Zc = 44
    base_mat_filename = "NR_1_7_30.txt"
    Zc = 30
    ###
    rayleigh = True
    EbNo_dB = 25
    num_blocks = 10
    ###
    offset = 0.35
    num_layers = 46
    num_iterations = 6
    ###
    base_mat = read_base_matrix(base_mat_filename)
    num_rows = base_mat.shape[0]
    num_cols = base_mat.shape[1]
    k = (num_cols - num_rows) * Zc
    n = num_cols * Zc
    code_rate = k / n
    EbNo_10 = 10 ** (EbNo_dB / 10)
    sigma = np.sqrt(1 / (2 * code_rate * EbNo_10))

    total_num_non_minus_1s = (base_mat != -1).sum()
    max_num_non_minus_1s_in_row = np.max(np.count_nonzero(base_mat != -1, axis=1))
    # row_minsum_storage = np.full((max_num_non_minus_1s_in_row, Zc), 0.0)
    row_minsum_storage = np.full((Zc, max_num_non_minus_1s_in_row), 0.0)

    start_time = time.time()
    print("########################################")
    total_num_errors = 0
    avg_num_errors_introduced = 0
    average_error = 0
    for i in range(0, num_blocks):
        print("\nBlock num: " + str(i))
        message = []
        for p in range(0, 22 * Zc):
            message.append(random.randint(0, 1))
        message = np.array(message)

        codeword = encode_message(base_mat, Zc, message)
        check = check_codeword(base_mat, Zc, codeword)
        # print("check: " + str(check))

        symbol = 1 - 2 * codeword

        if rayleigh == False:
            noise = np.random.randn(n)
            r = symbol + sigma * noise
            Beliefs = np.copy(r)
        else:
            #################### Rayleigh ####################
            fading_channel = np.array(
                1 / np.sqrt(2) * (np.random.randn(1, n) + 1j * np.random.randn(1, n))
            )  # Single tap flat rayleigh fading
            noise = np.array(
                np.random.randn(1, n) + 1j * np.random.randn(1, n)
            )  # 1/sqrt(2)* % AWGN noise
            rayl = np.array(fading_channel * symbol + sigma * noise)
            rayl = rayl / fading_channel
            r = np.real(rayl)
            abs_r = abs(r)
            dist_from_1 = 1 - abs_r
            abs_dist_from_1 = abs(dist_from_1)
            max_dist_from_1 = np.max(abs_dist_from_1)
            avg_r = np.average(abs_dist_from_1)
            average_error += avg_r
            Beliefs = np.copy(r[0, :])


            ###### count number of errors introduced ######
            rayl_noisy = (Beliefs < 0)
            error_count = 0
            error_indexes = []
            for (bpsk_bit, codeword_bit) in zip(rayl_noisy, codeword):
                if bpsk_bit != codeword_bit:
                    error_count += 1
                    # error_indexes.append()

            print(f"The number of errors introduced: {error_count}")
            print(f"The average error magnitude: {avg_r}")
            avg_num_errors_introduced += error_count

        #################### decoding ####################
        full_minsum_storage = np.full((Zc*total_num_non_minus_1s), 0.0) # 1D:len=(Zc*316)

        # divide into layers and run the following on the layers only
        rows_per_layer = (num_rows) / num_layers
        rows_per_layer = int(rows_per_layer)
        for iteration_count in range(0, num_iterations):
            full_minsum_index = 0
            for layer_num in range(0, num_layers):
                layer_index1 = layer_num * rows_per_layer
                layer_index2 = layer_index1 + rows_per_layer
                for current_row_num in range(layer_index1, layer_index2):
                    ############## start of layer ##############
                    row_minsum_index = 0 # (0:max of 19)
                    row_non_minus_1s_indexes = np.where(base_mat[current_row_num, :] != -1)[0]
                    for x in row_non_minus_1s_indexes:
                        subtract_list = full_minsum_storage[(full_minsum_index)*Zc:(full_minsum_index+1)*Zc] # 1D:len=(316*Zc)
                        Beliefs[(x) * Zc : (x + 1) * Zc] -= subtract_list
                        new_reg = shift_arr(Beliefs[(x)*Zc:(x+1)*Zc], base_mat[current_row_num, x])
                        row_minsum_storage[:, row_minsum_index] = new_reg.copy()
                        full_minsum_index += 1
                        row_minsum_index += 1
                    
                    non_min1s_in_row = row_minsum_index # current value is the number of non -1s in the current row in the layer.
                    full_minsum_index = full_minsum_index - row_minsum_index
                    row_minsum_index = 0

                    for x in range(0, Zc):  # offset minsum
                        temp_arr = row_minsum_storage[x, 0:non_min1s_in_row].copy() # 1D:len=non_min1s_in_row
                        min_arr = heapq.nsmallest(2, np.abs(temp_arr))
                        min_val_1 = min_arr[0]
                        min_val_2 = min_arr[1]
                        sign = np.sign(temp_arr)
                        sign = np.where(sign == 0, 1, sign)  # replace zero with a positive sign
                        overall_parity = np.prod(sign)
                        pos1 = np.where(np.abs(temp_arr) == heapq.nsmallest(2, np.abs(temp_arr))[0])[0]
                        # ############ Normalized MSA ############
                        # alpha = 0.8
                        # min_val_1 = alpha * min_val_1
                        # min_val_2 = alpha * min_val_2
                        ############## offset MSA ##############
                        min_val_1 = min_val_1 - offset
                        if min_val_1 < 0:
                            min_val_1 = 0
                        min_val_2 = min_val_2 - offset
                        if min_val_2 < 0:
                            min_val_2 = 0
                        ########################################
                        new_temp_reg = np.array(temp_arr)
                        new_temp_reg[:] = min_val_1
                        new_temp_reg[pos1] = min_val_2
                        temp_arr = overall_parity * sign * new_temp_reg
                        row_minsum_storage[x, 0:non_min1s_in_row] = temp_arr.copy() # shape (Zc;19)

                    for x in row_non_minus_1s_indexes:
                        shifted_list = shift_arr(row_minsum_storage[0:Zc, row_minsum_index], Zc - base_mat[current_row_num, x]) # 1D:len=Zc
                        full_minsum_storage[(full_minsum_index)*Zc:(full_minsum_index+1)*Zc] = shifted_list # 1D:len=Zc
                        add_list = full_minsum_storage[(full_minsum_index)*Zc:(full_minsum_index+1)*Zc] # 1D:len=Zc
                        Beliefs[(x) * Zc : (x + 1) * Zc] += add_list
                        full_minsum_index += 1
                        row_minsum_index += 1

        final_beliefs = Beliefs
        decoded_message = decode_to_binary(final_beliefs, k)
        errors_in_block = count_errors(message, decoded_message, Zc)
        print("errors_in_block = " + str(errors_in_block) + "\n")
        total_num_errors = total_num_errors + errors_in_block

    total_num_message_bits = num_blocks * k
    BER = total_num_errors / total_num_message_bits
    print("########################################")
    avg_num_errors_introduced = avg_num_errors_introduced/num_blocks
    print(f"the avg_num_errors_introduced = {avg_num_errors_introduced}")
    average_error /= num_blocks
    print(f"the average_error magnitude = {average_error}")
    print(f"the % of errors introduced = {(avg_num_errors_introduced/2040)*100}")

    print("########################################")
    print("num_blocks: " + str(num_blocks))
    print("num_layers: " + str(num_layers))
    print("num_iterations: " + str(num_iterations))
    print("EbNo_dB: " + str(EbNo_dB))
    print("total_num_errors: " + str(total_num_errors))
    print("total_num_message_bits: " + str(total_num_message_bits))
    print("BER: " + str(BER))
    print("########################################")
    end_time = time.time()
    runtime = end_time - start_time
    print("\nRuntime (sec): " + str(runtime))
    print("Runtime (min): " + str(runtime / 60))
    return


############################## helper functions ##############################
def shift_arr(row, x):
    arr = np.full(len(row), 0)
    if x != -1:
        y = []
        y.extend(row[x : len(row)])
        y.extend(row[0:x])
        arr = np.array(y)
    return arr

def count_errors(encoded, decoded, k):
    error_count = 0
    for j in range(0, k):
        if encoded[j] != decoded[j]:
            error_count = error_count + 1
    return error_count

def decode_to_binary(final_beliefs, k):
    temp_mat = np.full(len(final_beliefs), 69)
    for i in range(0, len(final_beliefs)):
        if final_beliefs[i] < 0:
            temp_mat[i] = 1
        else:
            temp_mat[i] = 0
    return temp_mat

def read_base_matrix(base_mat_name):
    file_dir = os.path.dirname(os.path.realpath(__file__))+"/"
    file_name = base_mat_name
    whole_dir = file_dir + file_name
    with open(whole_dir, "r") as file:
        full_list = []
        for line in file:
            line = line.strip("\n")
            line = line.strip(" ")
            line_list = []
            number = ""
            for i in range(0, len(line)):
                char = line[i]
                if char.isdigit():
                    if line[i - 1] == "-":
                        number = number + "-" + char
                        try:
                            if line[i + 1] == " ":
                                line_list.append(int(number))
                                number = ""
                        except IndexError:
                            line_list.append(int(number))
                            number = ""
                    else:
                        number = number + char
                        try:
                            if line[i + 1] == " ":
                                line_list.append(int(number))
                                number = ""
                        except IndexError:
                            line_list.append(int(number))
                            number = ""
            full_list.append(line_list)
    full_array = np.array(full_list)
    dimensions = full_array.shape
    # print("read_base_matrix() successful. Dimsensions:" +str(dimensions))
    return full_array

def check_codeword(base_mat, Zc, codeword):
    check = 0
    dimensions = base_mat.shape
    num_rows = dimensions[0]
    num_cols = dimensions[1]
    syndrome = np.full((num_rows * Zc, 1), 0)
    # codeword[4] = 0 # break_codeword
    count = 0
    for x in range(0, num_rows):
        for y in range(0, num_cols):
            trans_val = np.matrix(shift_arr(codeword[y * Zc : (y + 1) * Zc], base_mat[x, y])).T
            trans_val = np.array(trans_val)
            syndrome[x * Zc : (x + 1) * Zc] = (
                syndrome[x * Zc : (x + 1) * Zc] + trans_val
            ) % 2
            count += 1
    index_of_error = 0
    for x in syndrome:
        val = x
        if val != 0:
            print(
                "check failed, first error in codeword at index: " + str(index_of_error)
            )
            check = 1
            break
        index_of_error += 1
    return check

def encode_message(base_mat:list, Zc:int, message:list) -> list:
    """
    ONLY WORKS FOR Zc = 30 !!!!!!!!!!!!!!!!!!!!!!!!!!

    Generate a full codeword based on the parity matrix that is represented by
    the unexpanded base matrix. Do in place operations and dont create a fully
    expanded base matrix and work from that.

    :param base_mat: array of the base matrix. (46,68)
    :type base_mat: list

    :param Zc: base matrix expansion factor.
    :type Zc: int

    :param message: the message to encode.
    :type message: list

    :return: encoded message.
    :rtype: list
    """
    codeword = np.full(68*Zc, 0)
    codeword[0 : 22*Zc] = message
    codeword = np.array(codeword)

    parity_mat = np.full(Zc, 0)
    for x in range(0, 4): # encode P1
        for y in range(0, 22):
            shifted_list = shift_arr(message[(y) * Zc : (y + 1)*Zc], base_mat[x, y])
            parity_mat = parity_mat ^ shifted_list
    codeword[22*Zc : 23*Zc] = shift_arr(parity_mat, Zc)

    for x in range(0, 3): # encode P2-4
        parity_mat = np.full(Zc, 0)
        for y in range(0, 23 + x):
            shifted_list = shift_arr(codeword[(y) * Zc : (y + 1)*Zc], base_mat[x, y])
            parity_mat = parity_mat ^ shifted_list
        codeword[(23 + x)*Zc : (24 + x)*Zc] = parity_mat

    for x in range(4, 46):  # encode p5->end
        parity_mat = np.full(Zc, 0)
        for y in range(0, 26):
            shifted_list = shift_arr(codeword[(y) * Zc : (y + 1)*Zc], base_mat[x, y])
            parity_mat = parity_mat ^ shifted_list
        codeword[(22 + x)*Zc : (23 + x)*Zc] = parity_mat

    return codeword


main()
print("\n")
